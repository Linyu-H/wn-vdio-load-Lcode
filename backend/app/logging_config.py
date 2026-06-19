"""统一日志初始化。

为什么需要它：之前各模块都用 logging.getLogger("vdio.xxx") 打日志，但全局
从未配置过 handler，所有 logger.info/warning/error 实际都被丢弃 —— 排查
"YouTube 解析不了" 这类问题时根本没有线索。

本模块把 vdio.* 的日志同时写到：
  - 控制台（随 uvicorn 输出，开发时直接可见）
  - 轮转文件 logs/vdio.log（5MB × 5，便于事后排查、给用户看"成果"）

只在进程启动时调用一次 setup_logging()。
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.config import LOG_DIR, LOG_LEVEL

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def setup_logging() -> None:
    """初始化 vdio.* 日志。重复调用安全（只配置一次）。"""
    global _initialized
    if _initialized:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_DIR / "vdio.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # 只接管我们自己的命名空间，避免污染 uvicorn / yt-dlp 的日志配置
    root = logging.getLogger("vdio")
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)
    root.propagate = False  # 不向 root logger 冒泡，避免重复打印

    _initialized = True
    root.info("日志系统已初始化 level=%s file=%s", LOG_LEVEL, LOG_DIR / "vdio.log")
