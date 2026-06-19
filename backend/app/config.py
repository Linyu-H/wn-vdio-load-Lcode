"""全局配置。所有可调参数集中在此，便于本地/Docker 切换。"""
import os
from pathlib import Path

# 项目根目录下的 downloads 文件夹作为下载存储区
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", BASE_DIR / "downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 历史记录持久化文件
HISTORY_FILE = Path(os.getenv("HISTORY_FILE", BASE_DIR / "history.json"))

# 日志目录与级别。所有 vdio.* 日志写入 logs/vdio.log（轮转）并同时打印控制台。
LOG_DIR = Path(os.getenv("LOG_DIR", BASE_DIR / "logs"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# 代理：国内网络直连 YouTube / googlevideo 等海外站点通常被拦截（连接超时），
# 必须经代理访问。优先级：环境变量 YT_PROXY > 标准 HTTPS_PROXY/HTTP_PROXY/ALL_PROXY。
# 也可在 backend/proxy.txt 写一行代理地址（改后即时生效、无需重启），见 get_proxy()。
_ENV_PROXY = (
    os.getenv("YT_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    or os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or os.getenv("ALL_PROXY") or ""
).strip()
PROXY_FILE = Path(os.getenv("PROXY_FILE", BASE_DIR / "proxy.txt"))


def get_proxy() -> str:
    """返回当前代理地址（运行时可改）。proxy.txt 优先，便于不重启即时切换。"""
    try:
        if PROXY_FILE.exists():
            val = PROXY_FILE.read_text(encoding="utf-8").strip()
            if val and not val.startswith("#"):
                return val.splitlines()[0].strip()
    except Exception:
        pass
    return _ENV_PROXY

# 下载线程池大小（性能优先，可通过环境变量调高）
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))

# 单个已完成文件保留时长（秒），到期后清理；0 表示不按时长清理
FILE_TTL = int(os.getenv("FILE_TTL", "3600"))

# downloads 目录总容量上限（GB），超出按最旧优先清理；0 表示不限容量
DOWNLOAD_MAX_GB = float(os.getenv("DOWNLOAD_MAX_GB", "5"))

# 后台清理巡检间隔（秒）
CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", "600"))

# CORS 允许来源（开发期放开，部署可收紧）
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# yt-dlp cookies 文件（Netscape 格式）。存在则自动带上：
#  - 解锁 YouTube 720p/1080p（未登录态只给 360p）
#  - 绕过 "The page needs to be reloaded." 之类反爬
# 从已登录浏览器用扩展(如 "Get cookies.txt")导出 youtube 的 cookies.txt，
# 放到此默认路径，或用环境变量 YT_COOKIES 指定其它路径。
YT_COOKIES_FILE = os.getenv("YT_COOKIES", str(BASE_DIR / "youtube_cookies.txt"))

# yt-dlp 通用选项：超时、重试，降低偶发失败
YTDLP_BASE_OPTS = {
    "noplaylist": False,
    "socket_timeout": 30,
    "retries": 3,
    "quiet": True,
    "no_warnings": True,
    # 完整的headers配置，支持更多平台
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.bilibili.com/",
    },
}
