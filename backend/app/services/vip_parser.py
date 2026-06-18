"""VIP 解析源适配：提供预览地址与尽力提取直链能力。"""
from __future__ import annotations

import base64
import json
import re
import urllib.parse
import urllib.request
from urllib.parse import urlparse

from app.config import YTDLP_BASE_OPTS
from app.services.platform import detect_platform

VIP_PARSE_SOURCES = [
    {"id": "fongmi", "name": "默认A", "url": "https://json.fongmi.cc/web?url="},
    {"id": "playr", "name": "默认B", "url": "https://super.playr.top/?url="},
    {"id": "nodenode", "name": "Node解析", "url": "https://jx.nodenode.dpdns.org/?url="},
    {"id": "ckplayer", "name": "CK解析", "url": "https://www.ckplayer.vip/jiexi/?url="},
    {"id": "playerjy", "name": "Player-JY", "url": "https://jx.playerjy.com/?url="},
    {"id": "xmflv", "name": "虾米解析", "url": "https://jx.xmflv.com/?url="},
    {"id": "789", "name": "789解析", "url": "https://jiexi.789jiexi.icu:4433/?url="},
    {"id": "937", "name": "937解析", "url": "https://bfq.937auth.vip?url="},
    {"id": "hls", "name": "HLS解析", "url": "https://jx.hls.one/?url="},
    {"id": "speed", "name": "极速解析", "url": "https://jx.2s0.cn/player/?url="},
    {"id": "bingdou", "name": "冰豆解析", "url": "https://bd.jx.cn/?url="},
    {"id": "pouyun", "name": "剖元解析", "url": "https://www.pouyun.com/?url="},
    {"id": "973", "name": "973解析", "url": "https://jx.973973.xyz/?url="},
    {"id": "qige", "name": "七哥解析", "url": "https://jx.nnxv.cn/tv.php?url="},
    {"id": "playm3u8", "name": "playm3u8", "url": "https://www.playm3u8.cn/jiexi.php?url="},
    {"id": "qiqi", "name": "七七云解析", "url": "https://jx.77flv.cc/?url="},
    {"id": "mango", "name": "芒果TV1", "url": "https://video.isyour.love/player/getplayer?url="},
    {"id": "m1907", "name": "M1907", "url": "https://im1907.top/?jx="},
    {"id": "yparse", "name": "Yparse", "url": "https://jx.yparse.com/index.php?url="},
]

VIP_SUPPORTED_HOSTS = (
    "bilibili.com",
    "b23.tv",
    "v.qq.com",
    "m.v.qq.com",
    "iqiyi.com",
    "iq.com",
    "youku.com",
    "mgtv.com",
    "tudou.com",
    "tv.sohu.com",
    "film.sohu.com",
    "le.com",
    "pptv.com",
    "wasu.cn",
    "acfun.cn",
    "1905.com",
)

_MEDIA_RE = re.compile(r"https?:\\?/\\?/[^\"'<>\\]+?(?:\.m3u8|\.mp4)(?:\?[^\"'<>\\]*)?", re.IGNORECASE)
_URL_FIELD_RE = re.compile(r"(?:player_aaaa\s*=\s*\{[^}]*?|[\"']?url[\"']?\s*[:=]\s*)[\"']([^\"']+)[\"']", re.IGNORECASE | re.DOTALL)
_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")


def is_vip_supported_url(url: str) -> bool:
    try:
        host = (urlparse(url.strip()).netloc or "").lower()
    except ValueError:
        return False
    return any(supported in host for supported in VIP_SUPPORTED_HOSTS)


def get_vip_sources_for_url(url: str) -> list[dict]:
    if not is_vip_supported_url(url):
        return []
    return [
        {
            **source,
            "preview_url": source["url"] + urllib.parse.quote(url, safe=""),
        }
        for source in VIP_PARSE_SOURCES
    ]


def get_vip_sources() -> list[dict]:
    return [dict(source) for source in VIP_PARSE_SOURCES]


def get_source(source_id: str | None = None) -> dict:
    if source_id:
        for source in VIP_PARSE_SOURCES:
            if source["id"] == source_id:
                return source
    return VIP_PARSE_SOURCES[0]


def build_vip_preview_url(url: str, source_id: str | None = None) -> str | None:
    if not is_vip_supported_url(url):
        return None
    source = get_source(source_id)
    return source["url"] + urllib.parse.quote(url, safe="")


def build_vip_info(url: str, error: str | None = None) -> dict:
    platform = detect_platform(url)
    sources = get_vip_sources_for_url(url)
    return {
        "url": url,
        "title": platform["name"] if platform["platform"] != "unknown" else "VIP 视频",
        "thumbnail": None,
        "duration": None,
        "uploader": None,
        "platform": platform["platform"],
        "platform_name": platform["name"],
        "site_logo": _favicon_url(url),
        "preview_url": sources[0]["preview_url"] if sources else None,
        "vip_supported": True,
        "vip_preview_url": sources[0]["preview_url"] if sources else None,
        "vip_parse_sources": sources,
        "vip_parse_error": error,
        "qualities": [
            {"id": "720", "label": "默认", "height": 720},
            {"id": "1080", "label": "1080P", "height": 1080},
        ],
        "playlist_count": 0,
    }


def enrich_info(url: str, data: dict) -> dict:
    supported = is_vip_supported_url(url)
    sources = get_vip_sources_for_url(url) if supported else []
    data["vip_supported"] = supported
    data["vip_preview_url"] = sources[0]["preview_url"] if sources else None
    data["vip_parse_sources"] = sources
    return data


def extract_vip_direct_media(url: str, source_id: str | None = None) -> dict | None:
    """从 VIP 解析页尽力提取 m3u8/mp4 直链。失败返回 None。"""
    source_ids = [source_id] if source_id else [source["id"] for source in VIP_PARSE_SOURCES]
    for sid in filter(None, source_ids):
        source = get_source(sid)
        parser_url = build_vip_preview_url(url, source["id"])
        if not parser_url:
            continue
        html = _fetch_text(parser_url)
        candidates = _extract_candidates(html, parser_url)
        if not candidates:
            candidates = _extract_candidates(_try_ydlp_dump(parser_url), parser_url)
        if candidates:
            return {"url": candidates[0], "source": source, "parser_url": parser_url}
    return None


def _favicon_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"


def _fetch_text(url: str) -> str:
    headers = dict(YTDLP_BASE_OPTS.get("http_headers") or {})
    headers.setdefault("User-Agent", "Mozilla/5.0")
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.read(600_000).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_candidates(text: str, base_url: str) -> list[str]:
    if not text:
        return []
    expanded = [text, urllib.parse.unquote(text)]
    expanded.extend(_decode_base64_chunks(text))

    candidates = []
    for item in expanded:
        candidates.extend(_MEDIA_RE.findall(item))
        for match in _URL_FIELD_RE.findall(item):
            candidates.append(match)

    cleaned = []
    seen = set()
    for candidate in candidates:
        candidate = _clean_candidate(candidate, base_url)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        cleaned.append(candidate)
    return sorted(cleaned, key=_candidate_score, reverse=True)


def _decode_base64_chunks(text: str) -> list[str]:
    decoded = []
    for chunk in _BASE64_RE.findall(text):
        try:
            raw = base64.b64decode(chunk + "=" * (-len(chunk) % 4), validate=False)
            value = raw.decode("utf-8", errors="ignore")
        except Exception:
            continue
        if ".m3u8" in value or ".mp4" in value or "http" in value:
            decoded.append(value)
    return decoded


def _clean_candidate(candidate: str, base_url: str) -> str | None:
    candidate = candidate.strip().replace("\\/", "/")
    candidate = urllib.parse.unquote(candidate)
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    elif candidate.startswith("/"):
        parsed = urlparse(base_url)
        candidate = f"{parsed.scheme}://{parsed.netloc}{candidate}"
    if not candidate.startswith(("http://", "https://")):
        return None
    if ".m3u8" not in candidate.lower() and ".mp4" not in candidate.lower():
        return None
    return candidate


def _candidate_score(url: str) -> int:
    low = url.lower()
    score = 0
    if ".m3u8" in low:
        score += 20
    if ".mp4" in low:
        score += 10
    if "http" in low:
        score += 5
    return score


def _try_ydlp_dump(url: str) -> str:
    try:
        import yt_dlp
    except ImportError:
        return ""
    opts = dict(YTDLP_BASE_OPTS)
    opts.update({"skip_download": True, "quiet": True, "no_warnings": True})
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return ""
    return json.dumps(info, ensure_ascii=False)
