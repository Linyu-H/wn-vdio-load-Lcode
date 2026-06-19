"""无头浏览器抓流：加载 jx 解析页，拦截播放器实际请求的 m3u8/mp4 直链。

静态 HTML 爬取拿不到流地址（被 JS 动态加载/混淆），用 Playwright 跑真实浏览器，
监听网络响应，截取播放器真正请求的媒体直链 + 必要请求头，供下载阶段使用。
"""
from __future__ import annotations

import logging

logger = logging.getLogger("vdio.capture")

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 媒体直链特征：m3u8 优先（HLS 完整流），mp4 次之
_MEDIA_EXT = (".m3u8", ".mp4")
# 明显的非视频资源，跳过
_SKIP_HINT = ("/poster", "/cover", "thumbnail", "favicon", ".css", ".js?", "/ad/", "/ads/")


def _looks_like_media(url: str, content_type: str) -> bool:
    low = url.lower()
    if any(skip in low for skip in _SKIP_HINT):
        return False
    if any(ext in low for ext in _MEDIA_EXT):
        return True
    ct = (content_type or "").lower()
    return "mpegurl" in ct or ("video/" in ct and "mp4" in ct)


def _score(url: str) -> int:
    low = url.lower()
    score = 0
    if ".m3u8" in low:
        score += 30          # HLS 通常是完整可下流
    if ".mp4" in low:
        score += 20
    if "bilivideo" in low or "akamaized" in low or "cdn" in low:
        score += 5           # 命中常见 CDN，更可能是真实源
    return score


def capture_media(preview_url: str, timeout_ms: int = 28000) -> dict | None:
    """加载解析页并拦截媒体直链。返回 {'url','headers'} 或 None。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright 未安装，跳过无头抓流")
        return None

    hits: list[dict] = []

    def on_response(resp):
        try:
            ct = resp.headers.get("content-type", "")
            if _looks_like_media(resp.url, ct):
                req = resp.request
                hits.append({
                    "url": resp.url,
                    "headers": {
                        k: v for k, v in {
                            "Referer": req.headers.get("referer"),
                            "Origin": req.headers.get("origin"),
                            "User-Agent": req.headers.get("user-agent") or _UA,
                        }.items() if v
                    },
                })
        except Exception:
            pass

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(user_agent=_UA)
                page = ctx.new_page()
                page.on("response", on_response)
                try:
                    page.goto(preview_url, timeout=timeout_ms, wait_until="domcontentloaded")
                except Exception as e:
                    logger.info("capture goto warn: %s", str(e)[:80])
                page.wait_for_timeout(8000)
                try:  # 主动触发播放，逼出媒体请求
                    page.evaluate(
                        "document.querySelectorAll('video').forEach(v=>{v.muted=true;v.play&&v.play().catch(()=>{})})"
                    )
                except Exception:
                    pass
                page.wait_for_timeout(6000)
            finally:
                # 无论成功/超时/异常都关闭浏览器，避免泄漏 chromium 进程
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception as e:
        logger.warning("capture failed: %s", str(e)[:120])
        return None

    if not hits:
        return None
    # 去重 + 按可下载性打分排序
    seen, uniq = set(), []
    for h in sorted(hits, key=lambda x: _score(x["url"]), reverse=True):
        if h["url"] in seen:
            continue
        seen.add(h["url"])
        uniq.append(h)
    best = uniq[0]
    logger.info("capture ok url=%s headers=%s", best["url"][:100], list(best["headers"].keys()))
    return best
