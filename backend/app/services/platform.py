"""平台识别：根据 URL 域名判断来源平台，供前端展示专属图标。"""
import re
from urllib.parse import urlparse

# 域名关键字 -> (平台标识, 中文名)
_PLATFORM_RULES = [
    ("youtube.com", ("youtube", "YouTube")),
    ("youtu.be", ("youtube", "YouTube")),
    ("bilibili.com", ("bilibili", "哔哩哔哩")),
    ("b23.tv", ("bilibili", "哔哩哔哩")),
    ("douyin.com", ("douyin", "抖音")),
    ("iesdouyin.com", ("douyin", "抖音")),
    ("tiktok.com", ("tiktok", "TikTok")),
    ("twitter.com", ("twitter", "Twitter")),
    ("x.com", ("twitter", "Twitter")),
    ("instagram.com", ("instagram", "Instagram")),
    ("facebook.com", ("facebook", "Facebook")),
    ("vimeo.com", ("vimeo", "Vimeo")),
    ("v.qq.com", ("qq", "腾讯视频")),
    ("iqiyi.com", ("iqiyi", "爱奇艺")),
    ("iq.com", ("iqiyi", "爱奇艺")),
    ("youku.com", ("youku", "优酷")),
    ("mgtv.com", ("mgtv", "芒果TV")),
    ("sohu.com", ("sohu", "搜狐视频")),
    ("le.com", ("le", "乐视视频")),
    ("pptv.com", ("pptv", "PPTV")),
    ("1905.com", ("m1905", "1905电影网")),
    ("weibo.com", ("weibo", "微博")),
    ("xiaohongshu.com", ("xiaohongshu", "小红书")),
    ("kuaishou.com", ("kuaishou", "快手")),
]

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def is_valid_url(url: str) -> bool:
    """基础合法性校验：必须是 http/https 且能解析出 netloc。"""
    if not url or not _URL_RE.match(url.strip()):
        return False
    try:
        parsed = urlparse(url.strip())
        return bool(parsed.netloc)
    except ValueError:
        return False


def detect_platform(url: str) -> dict:
    """返回 {'platform': 标识, 'name': 中文名}。未知平台归为 unknown。"""
    host = ""
    try:
        host = (urlparse(url.strip()).netloc or "").lower()
    except ValueError:
        host = ""
    for keyword, (pid, name) in _PLATFORM_RULES:
        if keyword in host:
            return {"platform": pid, "name": name}
    return {"platform": "unknown", "name": host or "未知平台"}
