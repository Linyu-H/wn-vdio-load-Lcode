"""下载目录自动清理：按时长 + 总容量两条规则回收 downloads/。

为什么需要它：
- 服务端下载模式会把文件落到 downloads/，此前只增不减，长期必然撑爆磁盘。
- config 里早有 FILE_TTL 但从未接线，这里把它真正用起来，并补一条容量上限。

清理规则（cleanup_once）：
1. 时长：mtime 早于 FILE_TTL 的文件直接删（FILE_TTL=0 关闭）。
2. 容量：剩余文件总大小超过 DOWNLOAD_MAX_GB 时，按最旧优先删到达标（=0 关闭）。

安全保护：
- 跳过 yt-dlp 写入中的 .part / .ytdl 临时文件。
- 跳过最近 _GRACE 秒内修改过的文件，避免误删正在下载/刚完成待取的文件。
- 用 daemon 线程巡检，卡死也随进程退出，不拖累热重载（与 offload.py 一致）。
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from app.config import CLEANUP_INTERVAL, DOWNLOAD_DIR, DOWNLOAD_MAX_GB, FILE_TTL

logger = logging.getLogger("vdio.cleanup")

# 正在写入中不应被清理的文件后缀
_SKIP_SUFFIXES = (".part", ".ytdl", ".tmp")
# 最近修改过的文件保护窗口（秒）：避免误删正在下载/刚完成的文件。
# 必须小于默认 FILE_TTL(180s)，否则 3 分钟过期策略会被保护窗口抵消。
_GRACE = min(60, max(0, FILE_TTL // 3))

_stop = threading.Event()
_thread: threading.Thread | None = None


def _iter_files() -> list[Path]:
    try:
        return [p for p in DOWNLOAD_DIR.rglob("*") if p.is_file()]
    except Exception as e:  # 目录异常不应拖垮服务
        logger.warning("扫描下载目录失败: %s", e)
        return []


def _removable(path: Path, now: float) -> bool:
    if path.suffix.lower() in _SKIP_SUFFIXES:
        return False
    try:
        return (now - path.stat().st_mtime) > _GRACE
    except OSError:
        return False


def _delete(path: Path) -> int:
    """删除单个文件，返回回收的字节数（失败返回 0）。"""
    try:
        size = path.stat().st_size
        path.unlink()
        return size
    except OSError as e:
        logger.warning("删除失败 %s: %s", path.name, e)
        return 0


def cleanup_once() -> None:
    """执行一轮清理（时长 + 容量）。异常自包含，绝不抛出。"""
    now = time.time()
    freed = 0
    removed = 0

    # ── 规则 1：超时清理 ──
    if FILE_TTL > 0:
        for p in _iter_files():
            if p.suffix.lower() in _SKIP_SUFFIXES:
                continue
            try:
                age = now - p.stat().st_mtime
            except OSError:
                continue
            if age > FILE_TTL:
                got = _delete(p)
                if got:
                    freed += got
                    removed += 1

    # ── 规则 2：容量上限（最旧优先） ──
    if DOWNLOAD_MAX_GB > 0:
        cap = int(DOWNLOAD_MAX_GB * 1024 ** 3)
        files = []
        total = 0
        for p in _iter_files():
            try:
                st = p.stat()
            except OSError:
                continue
            files.append((st.st_mtime, st.st_size, p))
            total += st.st_size
        files.sort(key=lambda t: t[0])  # 旧→新
        for mtime, size, p in files:
            if total <= cap:
                break
            if not _removable(p, now):
                continue
            got = _delete(p)
            if got:
                total -= got
                freed += got
                removed += 1

    if removed:
        logger.info("清理完成：删除 %d 个文件，回收 %.1f MB", removed, freed / 1024 ** 2)


def _loop() -> None:
    # 启动先跑一轮，再按间隔巡检；_stop.wait 兼作可中断的 sleep
    while not _stop.is_set():
        try:
            cleanup_once()
        except Exception as e:  # 兜底，循环不被任何异常打断
            logger.warning("清理巡检异常: %s", e)
        _stop.wait(CLEANUP_INTERVAL)


def start() -> None:
    """启动后台清理线程（幂等）。"""
    global _thread
    if FILE_TTL <= 0 and DOWNLOAD_MAX_GB <= 0:
        logger.info("清理已禁用（FILE_TTL / DOWNLOAD_MAX_GB 均为 0）")
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="vdio-cleanup", daemon=True)
    _thread.start()
    logger.info(
        "清理线程已启动：TTL=%ss 容量上限=%sGB 间隔=%ss",
        FILE_TTL, DOWNLOAD_MAX_GB, CLEANUP_INTERVAL,
    )


def stop() -> None:
    """通知清理线程退出（daemon，进程退出也会自动回收）。"""
    _stop.set()
