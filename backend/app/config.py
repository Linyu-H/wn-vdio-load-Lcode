"""全局配置。所有可调参数集中在此，便于本地/Docker 切换。"""
import os
from pathlib import Path

# 项目根目录下的 downloads 文件夹作为下载存储区
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", BASE_DIR / "downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 历史记录持久化文件
HISTORY_FILE = Path(os.getenv("HISTORY_FILE", BASE_DIR / "history.json"))

# 下载线程池大小（性能优先，可通过环境变量调高）
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))

# 单个已完成文件保留时长（秒），到期后清理；0 表示不自动清理
FILE_TTL = int(os.getenv("FILE_TTL", "3600"))

# CORS 允许来源（开发期放开，部署可收紧）
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

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
