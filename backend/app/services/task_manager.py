"""异步任务管理器：task_id + 状态机 + 线程池。

下载是阻塞型 IO/CPU 混合任务，用线程池执行，避免阻塞 FastAPI 事件循环。
进度通过内存中的任务状态记录，WebSocket 端点轮询/订阅推送给前端。
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.config import MAX_WORKERS
from app.services import downloader
from app.services.offload import DaemonThreadPoolExecutor


class TaskStatus(str, Enum):
    WAITING = "waiting"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"   # 后处理(合并/转码)阶段
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class Task:
    id: str
    url: str
    quality: str
    audio_only: bool
    vip_source_id: Optional[str] = None
    status: TaskStatus = TaskStatus.WAITING
    progress: float = 0.0          # 0~100
    speed: Optional[str] = None    # 人类可读速度
    eta: Optional[int] = None      # 剩余秒数
    title: Optional[str] = None
    filename: Optional[str] = None
    filepath: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "quality": self.quality,
            "audio_only": self.audio_only,
            "vip_source_id": self.vip_source_id,
            "status": self.status.value,
            "progress": round(self.progress, 1),
            "speed": self.speed,
            "eta": self.eta,
            "title": self.title,
            "filename": self.filename,
            "error": self.error,
            "created_at": self.created_at,
        }


class TaskManager:
    def __init__(self, max_workers: int = MAX_WORKERS):
        # daemon 线程池：卡死的下载/抓流不会阻塞 uvicorn --reload 或进程退出
        self._executor = DaemonThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="vdio-download"
        )
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._on_complete = None  # 完成回调(用于写历史)

    def set_on_complete(self, cb):
        self._on_complete = cb

    def shutdown(self):
        """回收下载线程池：不等待卡死的下载/抓流（daemon 线程随进程销毁）。"""
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # 兜底：极旧版本无 cancel_futures
            self._executor.shutdown(wait=False)

    def create(self, url: str, quality: str, audio_only: bool, vip_source_id: str | None = None) -> Task:
        task = Task(id=uuid.uuid4().hex[:12], url=url, quality=quality, audio_only=audio_only, vip_source_id=vip_source_id)
        with self._lock:
            self._tasks[task.id] = task
        self._executor.submit(self._run, task)
        return task

    def get(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    def _make_hook(self, task: Task):
        """生成绑定到具体 task 的 yt-dlp 进度回调。"""
        def hook(d: dict):
            status = d.get("status")
            if status == "downloading":
                task.status = TaskStatus.DOWNLOADING
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                if total:
                    task.progress = downloaded / total * 100
                task.speed = d.get("_speed_str", "").strip() or None
                task.eta = d.get("eta")
            elif status == "finished":
                # 下载完，进入后处理(合并/转码)
                task.status = TaskStatus.PROCESSING
                task.progress = 99.0
        return hook

    def _run(self, task: Task):
        try:
            result = downloader.download(
                url=task.url,
                quality=task.quality,
                audio_only=task.audio_only,
                progress_hook=self._make_hook(task),
                vip_source_id=task.vip_source_id,
            )
            task.title = result["title"]
            task.filename = result["filename"]
            task.filepath = result["filepath"]
            task.progress = 100.0
            task.status = TaskStatus.COMPLETED
            if self._on_complete:
                try:
                    self._on_complete(task)
                except Exception:
                    pass
        except Exception as e:  # noqa: BLE001 — 下载失败原因多样，统一转友好提示
            task.status = TaskStatus.ERROR
            task.error = _friendly_error(str(e))


def _friendly_error(raw: str) -> str:
    """把 yt-dlp 冗长报错转成简短中文提示。"""
    low = raw.lower()
    # 已是中文友好提示（如 YouTube 限流）直接透传
    if "限流" in raw or "请等待" in raw:
        return raw[:120]
    if "rate-limited" in low or "rate limit" in low or "too many requests" in low or "429" in low:
        return "YouTube 暂时限流（短时间请求过多），请等待几分钟后再试"
    if "unsupported url" in low or "no video" in low:
        return "暂不支持该链接或链接无效"
    if "private" in low or "login" in low or "sign in" in low:
        return "该视频需要登录/为私有视频，无法下载"
    if "unavailable" in low or "removed" in low:
        return "视频不可用或已被删除"
    if "network" in low or "timed out" in low or "timeout" in low:
        return "网络超时，请重试"
    return "下载失败：" + raw[:120]


# 全局单例
task_manager = TaskManager()
