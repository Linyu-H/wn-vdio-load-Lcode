"""阻塞任务卸载：专用 daemon 线程池 + 超时 + 自动销毁。

为什么需要它：
- FastAPI 事件循环是单线程。async 路由里直接调用 yt-dlp / urllib / Playwright
  这类阻塞函数，会把整个服务卡死（曾导致登录卡死、热重载僵死、全站超时）。
  这里把阻塞调用统一丢到线程池执行，事件循环始终畅通。
- worker 线程全部 daemon：即便某个抓流/解析调用卡死，线程也随进程一起销毁，
  绝不会阻塞 uvicorn --reload 重启或进程退出。标准库的 ThreadPoolExecutor 线程
  是非 daemon，会在退出时 join 卡死的线程 —— 这正是之前热重载僵死的根因。
- run_blocking 带超时：调用方不会无限等待卡死的 worker。
"""
from __future__ import annotations

import asyncio
import atexit
import logging
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures.thread import _threads_queues, _worker

logger = logging.getLogger("vdio.offload")


class DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """worker 线程为 daemon 的线程池：卡死的阻塞调用不会拖住进程退出 / 热重载。

    仅重写线程创建处，把 t.daemon 设为 True 后再 start。内部实现随 CPython
    版本可能变化，若内部属性缺失则回退到标准（非 daemon）行为，保证不崩。
    """

    def _adjust_thread_count(self):  # noqa: D401 — 镜像 CPython 3.9 实现并强制 daemon
        try:
            if self._idle_semaphore.acquire(timeout=0):
                return

            def weakref_cb(_, q=self._work_queue):
                q.put(None)

            num_threads = len(self._threads)
            if num_threads < self._max_workers:
                thread_name = "%s_%d" % (self._thread_name_prefix or self, num_threads)
                t = threading.Thread(
                    name=thread_name,
                    target=_worker,
                    args=(
                        weakref.ref(self, weakref_cb),
                        self._work_queue,
                        self._initializer,
                        self._initargs,
                    ),
                )
                t.daemon = True  # ← 关键：daemon，随进程销毁，不阻塞 reload/退出
                t.start()
                self._threads.add(t)
                _threads_queues[t] = self._work_queue
        except AttributeError:
            super()._adjust_thread_count()


# 解析 / 探测 / 抓流共用的有界 daemon 线程池
_executor = DaemonThreadPoolExecutor(max_workers=6, thread_name_prefix="vdio-offload")


async def run_blocking(fn, *args, timeout: float | None = None, **kwargs):
    """在 daemon 线程池里执行阻塞函数，不阻塞事件循环。

    超时只让调用方停止等待（抛 asyncio.TimeoutError）；底层 daemon 线程会自然
    结束或随进程销毁，不会泄漏、也不会阻塞退出。
    """
    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))
    if timeout is None:
        return await fut
    return await asyncio.wait_for(fut, timeout=timeout)


def shutdown():
    """主动回收线程池：丢弃尚未开始的任务，不等待卡死的 worker。"""
    try:
        _executor.shutdown(wait=False, cancel_futures=True)
    except TypeError:  # 兜底：极旧版本无 cancel_futures
        _executor.shutdown(wait=False)


atexit.register(shutdown)
