"""yt-dlp 封装层：纯封装，不改动开源源码。

提供两个核心能力：
1. extract_info  —— 解析视频元信息(标题/封面/时长/可用画质)
2. download      —— 下载，带进度回调 hook

设计原则：把 yt-dlp 的复杂 options 收敛成简单的函数签名，
其余模块(任务管理器/API)只依赖这里暴露的函数。
"""
from __future__ import annotations

import re
import urllib.request
from typing import Callable, Optional
from urllib.parse import parse_qs, urljoin, urlparse

try:
    import imageio_ffmpeg
except ImportError:  # 本地未安装时仍可使用系统 ffmpeg 或只做信息解析
    imageio_ffmpeg = None
import yt_dlp

from app.config import DOWNLOAD_DIR, YTDLP_BASE_OPTS
from app.services.platform import detect_platform
from app.services.vip_parser import enrich_info, extract_vip_direct_media

# 画质档位 -> yt-dlp format 选择表达式
# 思路：优先取 <= 目标高度的最佳视频 + 最佳音频，回退到 best
_QUALITY_FORMATS = {
    "audio": "bestaudio/best",
    "240": "bestvideo[height<=240]+bestaudio/best[height<=240]/best",
    "360": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
    "480": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "720": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "4k": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
}

_BILIBILI_ORIGIN = "https://www.bilibili.com"
_ICON_RE = re.compile(
    r'<link[^>]+rel=["\'](?:[^"\']*\s)?(?:shortcut\s+icon|icon|apple-touch-icon)(?:\s[^"\']*)?["\'][^>]*>',
    re.IGNORECASE,
)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
_BVID_RE = re.compile(r"(BV[0-9A-Za-z]+)", re.IGNORECASE)


def _site_origin(url: str) -> str | None:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_bilibili_url(url: str) -> bool:
    """判断是否为 B 站链接，用于补充 B 站反爬需要的请求头。"""
    try:
        return "bilibili.com" in (urlparse(url.strip()).netloc or "").lower()
    except ValueError:
        return False


def _is_youtube_url(url: str) -> bool:
    try:
        host = (urlparse(url.strip()).netloc or "").lower()
    except ValueError:
        return False
    return "youtube.com" in host or "youtu.be" in host


def _ydlp_opts_for(url: str) -> dict:
    """复制通用 yt-dlp 配置，并按平台补充最小必要选项。"""
    opts = dict(YTDLP_BASE_OPTS)
    opts["http_headers"] = dict(YTDLP_BASE_OPTS.get("http_headers") or {})
    if imageio_ffmpeg is not None:
        opts["ffmpeg_location"] = imageio_ffmpeg.get_ffmpeg_exe()

    if _is_bilibili_url(url):
        # B 站 playurl 接口会校验 Origin 和当前视频页 Referer；只给站点根 Referer
        # 在部分视频上仍会返回 HTTP 412 Precondition Failed。
        opts["http_headers"].update({
            "Origin": _BILIBILI_ORIGIN,
            "Referer": url,
        })

    if _is_youtube_url(url):
        # YouTube 强制 SABR + 频繁改播放器签名，单一 web 客户端常拿不到带 URL 的格式。
        # 多客户端兜底（tv/ios/android/web_safari），最大化可用格式。
        opts["extractor_args"] = {
            "youtube": {"player_client": ["tv", "ios", "android", "web_safari", "default"]}
        }

    return opts


def _site_logo_url(url: str) -> str | None:
    """从站点首页自动抓 rel icon；失败时回退到 /favicon.ico。"""
    origin = _site_origin(url)
    if not origin:
        return None

    headers = dict(YTDLP_BASE_OPTS.get("http_headers") or {})
    headers.setdefault("User-Agent", "Mozilla/5.0")
    request = urllib.request.Request(origin, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            html = response.read(200_000).decode("utf-8", errors="ignore")
        for tag in _ICON_RE.findall(html):
            match = _HREF_RE.search(tag)
            if match:
                return urljoin(origin + "/", match.group(1))
    except Exception:
        pass

    return urljoin(origin + "/", "/favicon.ico")


def _bilibili_embed_url(url: str) -> str | None:
    match = _BVID_RE.search(url)
    if not match:
        return None

    try:
        query = parse_qs(urlparse(url).query)
    except ValueError:
        query = {}
    page = query.get("p", ["1"])[0] or "1"
    return f"https://player.bilibili.com/player.html?bvid={match.group(1)}&page={page}&autoplay=0"


def _youtube_embed_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    host = (parsed.netloc or "").lower()
    video_id = None
    if "youtu.be" in host:
        video_id = parsed.path.strip("/").split("/")[0]
    elif "youtube.com" in host:
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        if not video_id and parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/")[2]

    if video_id:
        return f"https://www.youtube.com/embed/{video_id}"
    return None


def _preview_url(url: str, info: dict) -> str:
    """优先返回平台播放器地址；未知平台回退到原视频页。"""
    return (
        _youtube_embed_url(url)
        or _bilibili_embed_url(url)
        or info.get("embed_url")
        or info.get("webpage_url")
        or url
    )


def has_embeddable_preview(url: str, info: dict) -> bool:
    preview = _preview_url(url, info)
    if not preview:
        return False
    return preview != url


def _human_quality_list(info: dict) -> list[dict]:
    """从 yt-dlp formats 提炼出去重的可下载画质列表，供前端可视化选择。

    按实际可用分辨率生成档位（含低清 240/360），避免低清视频无任何视频档位可选。
    """
    heights = set()
    has_audio_only = False
    for f in info.get("formats", []) or []:
        h = f.get("height")
        if h:
            heights.add(int(h))
        elif f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none"):
            has_audio_only = True

    available = []
    if has_audio_only or info.get("formats"):
        available.append({"id": "audio", "label": "纯音频", "height": 0})

    max_h = max(heights) if heights else 0
    # 仅提供 <= 实际最高分辨率的标准档位（含 240/360）
    for height, qid, label in [
        (240, "240", "240P"),
        (360, "360", "360P"),
        (480, "480", "480P"),
        (720, "720", "720P"),
        (1080, "1080", "1080P"),
        (2160, "4k", "4K"),
    ]:
        if max_h >= height - 40:
            available.append({"id": qid, "label": label, "height": height})

    # 至少保证有一个可选项
    if len(available) <= 1 and max_h == 0:
        available.append({"id": "720", "label": "默认", "height": 720})
    return available


def extract_info(url: str) -> dict:
    """解析视频信息，不下载。返回精简后的 dict。

    抛出 yt_dlp.utils.DownloadError 时由上层捕获转成友好错误。
    """
    opts = _ydlp_opts_for(url)
    opts["skip_download"] = True
    opts["socket_timeout"] = 8
    opts["retries"] = 1
    with yt_dlp.YoutubeDL(opts) as ydl:
        raw = ydl.extract_info(url, download=False)

    # 播放列表：取第一个条目展示，但保留 entries 数量提示
    entries = None
    if raw.get("_type") == "playlist":
        entries = raw.get("entries") or []
        first = entries[0] if entries else {}
        info = first
        playlist_count = len(entries)
    else:
        info = raw
        playlist_count = 0

    platform = detect_platform(url)
    return enrich_info(url, {
        "url": url,
        "title": info.get("title") or "未知标题",
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),  # 秒
        "uploader": info.get("uploader"),
        "platform": platform["platform"],
        "platform_name": platform["name"],
        "site_logo": _site_logo_url(url),
        "preview_url": _preview_url(url, info),
        "qualities": _human_quality_list(info),
        "playlist_count": playlist_count,
    })


def get_format_string(quality: str) -> str:
    """画质档位 -> yt-dlp format 表达式。未知档位回退到 1080。"""
    return _QUALITY_FORMATS.get(quality, _QUALITY_FORMATS["1080"])


def download(
    url: str,
    quality: str = "1080",
    audio_only: bool = False,
    progress_hook: Optional[Callable[[dict], None]] = None,
    outtmpl_dir=None,
    vip_source_id: str | None = None,
) -> dict:
    """下载视频/音频。

    progress_hook 接收 yt-dlp 原生进度 dict(含 status/downloaded_bytes/total_bytes 等)。
    返回 {'filepath': 最终文件路径, 'filename': 文件名, 'title': 标题}。
    """
    out_dir = outtmpl_dir or DOWNLOAD_DIR
    opts = _ydlp_opts_for(url)
    opts["noplaylist"] = True  # 下载阶段只下单个，避免误下整个列表
    opts["outtmpl"] = str(out_dir / "%(title).80s-%(id)s.%(ext)s")

    if audio_only or quality == "audio":
        opts["format"] = _QUALITY_FORMATS["audio"]
        # 转码为 mp3，便于通用播放
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        opts["format"] = get_format_string(quality)
        opts["merge_output_format"] = "mp4"

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # 计算最终文件名（postprocessor 可能改了扩展名）
            filepath = ydl.prepare_filename(info)
            if audio_only or quality == "audio":
                filepath = str(filepath).rsplit(".", 1)[0] + ".mp3"
    except Exception as original_error:
        direct = extract_vip_direct_media(url, vip_source_id)
        if not direct:
            raise RuntimeError("VIP 解析源没有提取到可下载直链，请切换解析源后重试") from original_error
        vip_opts = _ydlp_opts_for(direct["url"])
        vip_opts["outtmpl"] = str(out_dir / "%(title).80s-%(id)s.%(ext)s")
        vip_opts["noplaylist"] = True
        # 带上抓流阶段截到的请求头（部分 CDN 校验 Referer/Origin）
        captured_headers = direct.get("headers") or {}
        if captured_headers:
            vip_opts["http_headers"] = {**vip_opts.get("http_headers", {}), **captured_headers}
        if audio_only or quality == "audio":
            vip_opts["format"] = _QUALITY_FORMATS["audio"]
            vip_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            vip_opts["format"] = "bestvideo+bestaudio/best"
            vip_opts["merge_output_format"] = "mp4"
        if progress_hook:
            vip_opts["progress_hooks"] = [progress_hook]
        with yt_dlp.YoutubeDL(vip_opts) as ydl:
            info = ydl.extract_info(direct["url"], download=True)
            filepath = ydl.prepare_filename(info)
            if audio_only or quality == "audio":
                filepath = str(filepath).rsplit(".", 1)[0] + ".mp3"

    from pathlib import Path
    fp = Path(filepath)
    return {
        "filepath": str(fp),
        "filename": fp.name,
        "title": info.get("title") or "未知标题",
    }


def get_direct_url(url: str, quality: str = "1080") -> dict:
    """模式B：只解析直链，不下载。返回可直接播放/下载的直链。

    部分平台(如需要鉴权/分片的)可能拿不到单一直链，此时 direct_url 为 None。
    """
    opts = _ydlp_opts_for(url)
    opts["skip_download"] = True
    opts["noplaylist"] = True
    opts["format"] = get_format_string(quality)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    direct = info.get("url")  # 单一直链(已选定 format 时通常存在)
    return {
        "direct_url": direct,
        "title": info.get("title") or "未知标题",
        "ext": info.get("ext"),
    }
