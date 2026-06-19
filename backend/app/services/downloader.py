"""yt-dlp 封装层：纯封装，不改动开源源码。

提供两个核心能力：
1. extract_info  —— 解析视频元信息(标题/封面/时长/可用画质)
2. download      —— 下载，带进度回调 hook

设计原则：把 yt-dlp 的复杂 options 收敛成简单的函数签名，
其余模块(任务管理器/API)只依赖这里暴露的函数。
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

try:
    import imageio_ffmpeg
except ImportError:  # 本地未安装时仍可使用系统 ffmpeg 或只做信息解析
    imageio_ffmpeg = None
import yt_dlp

from app.config import DOWNLOAD_DIR, YT_COOKIES_FILE, YTDLP_BASE_OPTS, get_proxy
from app.services.cookie_store import cookie_store
from app.services.platform import detect_platform
from app.services.vip_parser import enrich_info, extract_vip_direct_media

logger = logging.getLogger("vdio.downloader")

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


def _is_douyin_url(url: str) -> bool:
    try:
        host = (urlparse(url.strip()).netloc or "").lower()
    except ValueError:
        return False
    return "douyin.com" in host or "iesdouyin.com" in host


def _is_twitter_url(url: str) -> bool:
    try:
        host = (urlparse(url.strip()).netloc or "").lower()
    except ValueError:
        return False
    return "twitter.com" in host or "x.com" in host


def _ffmpeg_bin() -> str | None:
    if imageio_ffmpeg is not None:
        return imageio_ffmpeg.get_ffmpeg_exe()
    return "ffmpeg"


def _ffprobe_available() -> bool:
    """yt-dlp 的合并/转码后处理需要 ffprobe；imageio-ffmpeg 只带 ffmpeg 不带 ffprobe。"""
    ffmpeg = _ffmpeg_bin()
    candidates = []
    if ffmpeg:
        candidates.append(str(Path(ffmpeg).with_name("ffprobe")))
    candidates.append("ffprobe")
    for cmd in candidates:
        try:
            subprocess.run([cmd, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            return True
        except Exception:
            continue
    return False


def _faststart_mp4(path: str) -> None:
    """把 mp4 moov 元数据移到文件头，便于浏览器边下边播。

    只做 stream copy，不转码，CPU/耗时很低；失败不影响下载文件本身。
    """
    if not str(path).lower().endswith(".mp4"):
        return
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        return
    src = Path(path)
    tmp = src.with_suffix(src.suffix + ".faststart")
    try:
        subprocess.run(
            [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-c", "copy", "-movflags", "+faststart", str(tmp)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
        tmp.replace(src)
    except Exception as e:  # noqa: BLE001
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        logger.warning("mp4 faststart 处理失败 file=%s err=%s", src.name, str(e)[:120])


# cookies 失效 / 需要登录的典型报错特征（命中则触发去 cookies 兜底）
_YT_AUTH_FAIL_HINTS = (
    "sign in", "log in", "login", "cookies", "consent", "captcha",
    "the page needs to be reloaded", "confirm you're not a bot", "not a bot",
    "private video", "members-only",
)

# bot 风控墙特征。这是 YouTube 服务端主动防抓，去掉 cookies 只会更糟——
# 此时正确做法是【保留 cookies】换更宽客户端集合重试，而非现有的去 cookies 兜底。
_YT_BOT_WALL_HINTS = (
    "confirm you're not a bot", "confirm you’re not a bot", "not a bot",
    "sign in to confirm",
)

# 被 YouTube 限流的特征。命中时立即停手并给出友好提示——
# 此时继续重试只会加重限流、把冷却期越拖越长。
_YT_RATE_LIMIT_HINTS = (
    "rate-limited", "rate limit", "too many requests",
    "http error 429", "this content isn't available, try again later",
)

# 连接层失败特征（连不上 / 超时 / DNS 解析失败 / 连接被重置）。
# 国内直连 YouTube/googlevideo 通常就是这类——必须配代理，而不是改解析参数。
_YT_NETWORK_HINTS = (
    "timed out", "timeout", "getaddrinfo", "failed to resolve", "name or service not known",
    "network is unreachable", "no route to host", "connection refused",
    "connection reset", "connection aborted", "connection timed out",
    "tunnel connection failed", "proxy", "10060", "10054",
    "read timed out", "winerror", "max retries exceeded",
)

# ── YouTube 客户端策略（2026，关键修复） ───────────────────────────
# 实测(yt-dlp 2025.10.14)：android_vr 单客户端即可拿到完整画质(到 4K)，
# 且无需 cookies / PO token。只用 1 个客户端 = 1 次 player 请求。
#
# 旧配置 ["android_vr","android","default"] 会让 yt-dlp 逐个请求并合并，
# 叠加 cookies/去cookies 双兜底，单次解析就是 3~6 个请求；连点几次即触发
# "The current session has been rate-limited by YouTube" —— 这正是
# "YouTube 解析不了" 的真正根因（而非画质或客户端本身的问题）。
_YT_PRIMARY_CLIENTS = ["android_vr"]
# 主客户端失败时的兜底集合：仍只用免 PO token 可用的客户端。
_YT_FALLBACK_CLIENTS = ["android_vr", "android", "default"]


def _cookie_file_for(url: str) -> str | None:
    """按 URL 所属平台解析可用的 cookie 文件；无则 None（走匿名解析）。

    优先用管理端 cookie_store 里对应平台的 cookie；YouTube 额外回退到旧版单文件。
    """
    platform = detect_platform(url)["platform"]
    path = cookie_store.path_for(platform)
    if path:
        return path
    if _is_youtube_url(url) and YT_COOKIES_FILE and os.path.exists(YT_COOKIES_FILE):
        return YT_COOKIES_FILE
    return None


def _yt_cookies_present(url: str | None = None) -> bool:
    if url is not None:
        return _cookie_file_for(url) is not None
    return bool(YT_COOKIES_FILE) and os.path.exists(YT_COOKIES_FILE)


def _looks_like_auth_failure(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(hint in msg for hint in _YT_AUTH_FAIL_HINTS)


def _is_rate_limited(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(hint in msg for hint in _YT_RATE_LIMIT_HINTS)


def _is_bot_wall(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(hint in msg for hint in _YT_BOT_WALL_HINTS)


def _bot_wall_message(url: str | None = None) -> str:
    """撞 YouTube bot 风控墙时的可执行提示。

    根因是 YouTube 服务端风控（与 yt-dlp 版本时效强相关），代码无法根除，
    给用户三条真实可行的处置路径。
    """
    has_cookies = _yt_cookies_present(url) if url is not None else _yt_cookies_present()
    tips = []
    if not has_cookies:
        tips.append("在管理端导入新鲜的 YouTube cookies（从已登录浏览器导出）")
    else:
        tips.append("更新 YouTube cookies（当前 cookies 可能已过期或非登录态）")
    tips.append("升级 yt-dlp 到最新版（pip install -U --pre yt-dlp，旧版绕过手段会被风控收紧）")
    tips.append("更换代理出口 IP（当前出口可能已被标记）")
    return "YouTube 触发了机器人验证。可尝试：" + "；".join(f"{i + 1}.{t}" for i, t in enumerate(tips))


def _is_network_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(hint in msg for hint in _YT_NETWORK_HINTS)


def _network_error_message(exc: Exception | None = None) -> str:
    """连不上 YouTube 时的可执行提示，区分三种情形：
    1) 配了代理但连接被拒绝 → 代理软件没开 / 端口写错（最常见的踩坑）
    2) 配了代理但仍超时       → 代理本身连不上海外
    3) 完全没配代理           → 国内直连被拦截，指路配置代理
    """
    proxy = get_proxy()
    msg = str(exc).lower() if exc is not None else ""
    if proxy:
        if "refused" in msg or "10061" in msg:
            return (
                f"代理连接被拒绝（{proxy}）。多半是代理软件没启动、或端口写错了。"
                "请确认代理软件正在运行，并把它实际监听的端口写进 backend/proxy.txt"
            )
        return (
            f"经代理（{proxy}）仍无法连接 YouTube。请确认代理能访问海外站点，"
            "或在 backend/proxy.txt 更换可用代理后重试"
        )
    return (
        "无法连接 YouTube（国内网络通常被拦截）。请配置代理：在 backend/proxy.txt "
        "写入一行如 http://127.0.0.1:7890（端口按你的代理软件实际监听端口），或设环境变量 "
        "YT_PROXY 后重启后端"
    )


def _ydlp_opts_for(url: str, *, use_cookies: bool = True, yt_clients: list[str] | None = None) -> dict:
    """复制通用 yt-dlp 配置，并按平台补充最小必要选项。

    use_cookies=False 用于失败兜底：不带 cookies 重新解析。
    yt_clients 指定 YouTube player_client（默认走单客户端，降低限流概率）。
    """
    opts = dict(YTDLP_BASE_OPTS)
    opts["http_headers"] = dict(YTDLP_BASE_OPTS.get("http_headers") or {})
    if imageio_ffmpeg is not None:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        # 给 yt-dlp 传目录而非单个 ffmpeg 文件；若系统/目录里有 ffprobe，后处理才能探测音频编码。
        opts["ffmpeg_location"] = str(Path(ffmpeg).parent)

    # 有对应平台 cookie 且本次允许使用就带上：解锁登录内容/高清、绕过部分反爬。
    # yt-dlp 按域名自动匹配，对非对应站点无副作用。
    has_cookies = False
    if use_cookies:
        cookie_file = _cookie_file_for(url)
        if cookie_file:
            opts["cookiefile"] = cookie_file
            has_cookies = True

    if _is_bilibili_url(url):
        # B 站 playurl 接口会校验 Origin 和当前视频页 Referer；只给站点根 Referer
        # 在部分视频上仍会返回 HTTP 412 Precondition Failed。
        opts["http_headers"].update({
            "Origin": _BILIBILI_ORIGIN,
            "Referer": url,
        })

    if _is_douyin_url(url):
        # 抖音 CDN 会校验 Referer。通用配置里的 B 站 Referer 会导致媒体直链下载 403，
        # 解析可以成功但下载失败；这里改成抖音站点来源。
        opts["http_headers"].update({
            "Origin": "https://www.douyin.com",
            "Referer": "https://www.douyin.com/",
        })

    if _is_twitter_url(url):
        # X/Twitter 的 video.twimg.com 直链会校验来源；全局 B 站 Referer 会导致 403 Unauthorized。
        opts["http_headers"].update({
            "Origin": "https://x.com",
            "Referer": "https://x.com/",
        })

    if _is_youtube_url(url):
        # 单客户端策略：android_vr 免 cookies/PO token 即可拿到完整画质，
        # 且把 player 请求数压到最小，规避 "session has been rate-limited"。
        opts["extractor_args"] = {
            "youtube": {"player_client": yt_clients or _YT_PRIMARY_CLIENTS}
        }
        # 限制提取重试，避免个别客户端异常时把解析请求拖到 40s+
        opts["extractor_retries"] = 1
        # 轻度请求节流：yt-dlp 内部多请求之间留间隔，进一步降低被限流概率
        opts["sleep_interval_requests"] = 0.4
        # base headers 里的 B 站 Referer 不该带到 YouTube，去掉以免成为反爬特征
        opts["http_headers"].pop("Referer", None)
        # 国内直连 YouTube 多被拦截，配了代理就带上（仅作用于海外站点）
        proxy = get_proxy()
        if proxy:
            opts["proxy"] = proxy

    return opts


def _site_logo_url(url: str) -> str | None:
    """返回站点主域名下的 /favicon.ico。

    主站 favicon 比首页 <link rel=icon> 抓到的 CDN 图标更可靠：后者常带防盗链/
    referer 限制，浏览器加载会 403 而回退到 emoji；而且实时爬首页还会被反爬拦
    （B 站会返回验证码页），既慢又不稳。与 VIP 路径(_favicon_url)保持一致。
    """
    origin = _site_origin(url)
    if not origin:
        return None
    return f"{origin}/favicon.ico"


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


def _youtube_video_id(url: str) -> str | None:
    """提取 YouTube 单视频 ID；watch 带 list= 时也只认当前 v。"""
    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    host = (parsed.netloc or "").lower()
    if "youtu.be" in host:
        return parsed.path.strip("/").split("/")[0] or None
    if "youtube.com" in host:
        query = parse_qs(parsed.query)
        video_id = query.get("v", [None])[0]
        if video_id:
            return video_id
        if parsed.path.startswith("/shorts/"):
            parts = parsed.path.split("/")
            return parts[2] if len(parts) > 2 else None
    return None


def _youtube_embed_url(url: str) -> str | None:
    video_id = _youtube_video_id(url)
    if video_id:
        return f"https://www.youtube.com/embed/{video_id}"
    return None


def _douyin_video_id(url: str) -> str | None:
    """提取抖音视频 ID；兼容 /video/{id} 和精选页 modal_id={id}。"""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None

    match = re.search(r"/video/(\d+)", parsed.path or "")
    if match:
        return match.group(1)
    modal_id = parse_qs(parsed.query).get("modal_id", [None])[0]
    if modal_id and modal_id.isdigit():
        return modal_id
    return None


def _normalize_extractor_url(url: str) -> str:
    """把平台分享/列表/弹窗 URL 归一成 yt-dlp 支持的单视频 URL。"""
    if _is_youtube_url(url):
        video_id = _youtube_video_id(url)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
    if _is_douyin_url(url):
        video_id = _douyin_video_id(url)
        if video_id:
            return f"https://www.douyin.com/video/{video_id}"
    return url


def _preview_url(url: str, info: dict) -> str | None:
    """优先返回确定可嵌入的平台播放器；没有 embed 就交给前端展示封面。

    直接把原视频页塞进 iframe 很多平台会被 X-Frame-Options / CSP 拒绝
    （例如抖音会显示 refused to connect），所以不能把 webpage_url/url 当预览兜底。
    """
    return (
        _youtube_embed_url(url)
        or _bilibili_embed_url(url)
        or info.get("embed_url")
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
    # socket_timeout：代理通时 player 请求约 2-3s 即返回；给到 15s 容忍代理握手抖动，
    # 又远小于上层 PARSE_TIMEOUT(45s)，不会把"真超时"误判成"慢"。
    overrides = {"skip_download": True, "socket_timeout": 15, "retries": 0}
    is_yt = _is_youtube_url(url)

    # YouTube 音乐电台 / playlist 链接常带 list=RD...。解析视频信息时只需要当前 v，
    # 保留 list 会先进入 youtube:tab 播放列表提取器，额外请求整列数据，国内/代理环境下容易拖到
    # API 层 45s 超时。下载阶段本来就 noplaylist=True；这里提前归一化为单视频 URL。
    ydl_url = _normalize_extractor_url(url)

    def _attempt(use_cookies: bool, yt_clients: list[str] | None = None) -> dict:
        opts = _ydlp_opts_for(ydl_url, use_cookies=use_cookies, yt_clients=yt_clients)
        opts.update(overrides)
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(ydl_url, download=False)

    t0 = time.time()
    if is_yt:
        logger.info(
            "yt extract 开始 url=%s cookies=%s proxy=%s client=%s",
            url, _yt_cookies_present(url), bool(get_proxy()), _YT_PRIMARY_CLIENTS,
        )

    try:
        raw = _attempt(use_cookies=True)
    except Exception as e:
        if is_yt and _is_network_error(e):
            # 连不上 YouTube（多为国内直连被拦截 / 代理没开）：再试只是重复超时，
            # 直接快速失败并按具体网络错误指路（代理被拒 / 代理超时 / 没配代理）
            logger.error("yt extract 连接失败 proxy=%s 用时=%.1fs err=%s",
                         bool(get_proxy()), time.time() - t0, str(e)[:160])
            raise RuntimeError(_network_error_message(e)) from e
        if is_yt and _is_rate_limited(e):
            # 限流时再重试只会越拖越久：直接停手，给用户可执行的提示
            logger.error("yt extract 被限流 url=%s err=%s", url, str(e)[:160])
            raise RuntimeError(
                "YouTube 暂时限流（短时间请求过多），请等待几分钟后再试"
            ) from e
        if is_yt:
            # 主尝试失败：撞 bot 风控墙时【保留 cookies】换更宽客户端集合重试
            # （去 cookies 反而更易被墙）；其余失败才走去 cookies 兜底。
            keep_cookies = _is_bot_wall(e) and _yt_cookies_present(url)
            logger.warning(
                "yt extract 主尝试失败，启用兜底(%s+多客户端) url=%s err=%s",
                "保留cookies" if keep_cookies else "去cookies", url, str(e)[:160],
            )
            try:
                raw = _attempt(use_cookies=keep_cookies, yt_clients=_YT_FALLBACK_CLIENTS)
            except Exception as e2:
                if _is_network_error(e2):
                    logger.error("yt extract 兜底连接失败 url=%s", url)
                    raise RuntimeError(_network_error_message(e2)) from e2
                if _is_rate_limited(e2):
                    logger.error("yt extract 兜底也被限流 url=%s", url)
                    raise RuntimeError(
                        "YouTube 暂时限流（短时间请求过多），请等待几分钟后再试"
                    ) from e2
                if _is_bot_wall(e2):
                    logger.error("yt extract 兜底撞 bot 墙 url=%s", url)
                    raise RuntimeError(_bot_wall_message(url)) from e2
                logger.error("yt extract 兜底失败 url=%s err=%s", url, str(e2)[:160])
                raise
        else:
            raise

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

    if is_yt:
        heights = sorted({f.get("height") for f in (info.get("formats") or []) if f.get("height")})
        logger.info(
            "yt extract 成功 url=%s title=%r heights=%s 用时=%.1fs",
            url, (info.get("title") or "")[:40], heights, time.time() - t0,
        )

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
    extra = {
        "noplaylist": True,  # 下载阶段只下单个，避免误下整个列表
        "outtmpl": str(out_dir / "%(title).80s-%(id)s.%(ext)s"),
    }

    if audio_only or quality == "audio":
        extra["format"] = _QUALITY_FORMATS["audio"]
        if _ffprobe_available():
            # 转码为 mp3，便于通用播放；需要 ffprobe 判断源音频编码。
            extra["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            # 本机未安装 ffprobe 时不做后处理转码，直接下载原始音频，避免任务失败。
            # Docker 镜像 apt 安装 ffmpeg，会自带 ffprobe，仍会走 mp3 转码。
            logger.warning("ffprobe 不可用：音频下载跳过 mp3 转码，保留源格式")
    else:
        extra["format"] = get_format_string(quality)
        extra["merge_output_format"] = "mp4"

    if progress_hook:
        extra["progress_hooks"] = [progress_hook]

    is_yt = _is_youtube_url(url)

    ydl_url = _normalize_extractor_url(url)

    if _is_douyin_url(ydl_url) and not (audio_only or quality == "audio"):
        # 抖音默认 best 经常选到 bytevc1/h265，下载能成功但浏览器 video 可能无法播放。
        # 为了本站临时在线播放优先选 h264+aac 的 mp4；没有 h264 时再回退 best。
        target_h = 2160 if quality == "4k" else int(quality) if str(quality).isdigit() else 1080
        extra["format"] = (
            f"best[height<={target_h}][vcodec=h264]/"
            f"best[height<={target_h}][vcodec^=avc1]/"
            f"best[vcodec=h264]/best[vcodec^=avc1]/best"
        )
        extra["merge_output_format"] = "mp4"

    def _attempt(use_cookies: bool, yt_clients: list[str] | None = None):
        opts = _ydlp_opts_for(ydl_url, use_cookies=use_cookies, yt_clients=yt_clients)
        opts.update(extra)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(ydl_url, download=True)
            return info, ydl.prepare_filename(info)

    if is_yt:
        logger.info("yt download 开始 url=%s quality=%s audio=%s", url, quality, audio_only)

    try:
        try:
            info, filepath = _attempt(use_cookies=True)
        except Exception as e:
            if is_yt and _is_network_error(e):
                logger.error("yt download 连接失败 proxy=%s err=%s", bool(get_proxy()), str(e)[:160])
                raise RuntimeError(_network_error_message(e)) from e
            if is_yt and _is_rate_limited(e):
                logger.error("yt download 被限流 url=%s err=%s", url, str(e)[:160])
                raise RuntimeError(
                    "YouTube 暂时限流（短时间请求过多），请等待几分钟后再试"
                ) from e
            if is_yt:
                # 撞 bot 墙时保留 cookies 重试（去 cookies 更易被墙）；其余失败才去 cookies
                keep_cookies = _is_bot_wall(e) and _yt_cookies_present(url)
                logger.warning(
                    "yt download 主尝试失败，启用兜底(%s) url=%s err=%s",
                    "保留cookies" if keep_cookies else "去cookies", url, str(e)[:160]
                )
                try:
                    info, filepath = _attempt(use_cookies=keep_cookies, yt_clients=_YT_FALLBACK_CLIENTS)
                except Exception as e2:
                    if _is_bot_wall(e2):
                        logger.error("yt download 兜底撞 bot 墙 url=%s", url)
                        raise RuntimeError(_bot_wall_message(url)) from e2
                    raise
            else:
                raise
        # 计算最终文件名（postprocessor 可能改了扩展名）
        if audio_only or quality == "audio":
            filepath = str(filepath).rsplit(".", 1)[0] + ".mp3"
        if is_yt:
            logger.info("yt download 成功 url=%s file=%s", url, os.path.basename(str(filepath)))
        _faststart_mp4(str(filepath))
    except Exception as original_error:
        # YouTube 和 X/Twitter 都没有 VIP 解析兜底；直接抛出真实错误，
        # 避免被覆盖成 "VIP 解析源没有提取到可下载直链" 的误导提示。
        if is_yt or _is_twitter_url(url):
            raise
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
            if _ffprobe_available():
                vip_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            else:
                logger.warning("ffprobe 不可用：VIP 音频下载跳过 mp3 转码，保留源格式")
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
        _faststart_mp4(str(filepath))

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
