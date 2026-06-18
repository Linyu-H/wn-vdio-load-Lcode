"""通用上下集导航。

- B 站番剧：调 season API（ep_id）取整季剧集
- B 站多 P 视频：yt-dlp playlist / pagelist
- 其他平台：优雅降级（返回单集，前端隐藏上下集按钮）
"""
from __future__ import annotations

import json
import re
import urllib.request
from urllib.parse import urlparse

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_EP_RE = re.compile(r"/bangumi/play/ep(\d+)", re.IGNORECASE)
_SS_RE = re.compile(r"/bangumi/play/ss(\d+)", re.IGNORECASE)
_BV_RE = re.compile(r"(BV[0-9A-Za-z]+)")


def _fetch_json(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None


def get_episodes(url: str) -> dict:
    """返回 {'type', 'episodes': [{title, url, id}], 'current_index'}。

    episodes 为空或长度 1 时前端不显示上下集按钮。
    """
    host = (urlparse(url.strip()).netloc or "").lower()

    if "bilibili.com" in host and "/bangumi/play/" in url:
        result = _bilibili_bangumi(url)
        if result:
            return result

    if "bilibili.com" in host and "/video/" in url:
        result = _bilibili_video(url)
        if result:
            return result

    return {"type": "single", "episodes": [], "current_index": -1}


def _bilibili_bangumi(url: str) -> dict | None:
    ep_match = _EP_RE.search(url)
    ss_match = _SS_RE.search(url)
    if ep_match:
        api = f"https://api.bilibili.com/pgc/view/web/season?ep_id={ep_match.group(1)}"
        current_ep = int(ep_match.group(1))
    elif ss_match:
        api = f"https://api.bilibili.com/pgc/view/web/season?season_id={ss_match.group(1)}"
        current_ep = None
    else:
        return None

    data = _fetch_json(api)
    if not data or data.get("code") != 0:
        return None

    raw_eps = (data.get("result") or {}).get("episodes") or []
    episodes = []
    current_index = -1
    for idx, ep in enumerate(raw_eps):
        ep_id = ep.get("id")
        link = ep.get("link") or f"https://www.bilibili.com/bangumi/play/ep{ep_id}"
        # 标题：优先"第N话 + 长标题"
        short = (ep.get("title") or "").strip()
        long_t = (ep.get("long_title") or "").strip()
        label = f"第{short}话" if short and short.isdigit() else (short or f"EP{idx + 1}")
        if long_t:
            label = f"{label} {long_t}"
        episodes.append({"id": str(ep_id), "title": label.strip(), "url": link})
        if current_ep is not None and ep_id == current_ep:
            current_index = idx

    if current_index == -1 and episodes:
        current_index = 0
    return {"type": "bangumi", "episodes": episodes, "current_index": current_index}


def _bilibili_video(url: str) -> dict | None:
    """多 P 视频：用 view API 取分 P 列表。单 P 则返回 None（无需上下集）。"""
    bv = _BV_RE.search(url)
    if not bv:
        return None
    api = f"https://api.bilibili.com/x/web-interface/view?bvid={bv.group(1)}"
    data = _fetch_json(api)
    if not data or data.get("code") != 0:
        return None

    pages = (data.get("data") or {}).get("pages") or []
    if len(pages) <= 1:
        return None  # 单 P，不需要上下集

    bvid = bv.group(1)
    episodes = []
    for p in pages:
        page_num = p.get("page")
        episodes.append({
            "id": f"{bvid}-p{page_num}",
            "title": p.get("part") or f"P{page_num}",
            "url": f"https://www.bilibili.com/video/{bvid}/?p={page_num}",
        })

    # 当前 P：URL 里的 ?p=，默认 1
    current_p = 1
    m = re.search(r"[?&]p=(\d+)", url)
    if m:
        current_p = int(m.group(1))
    current_index = max(0, min(current_p - 1, len(episodes) - 1))
    return {"type": "multipart", "episodes": episodes, "current_index": current_index}
