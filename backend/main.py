"""FastAPI 应用主入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 日志必须最先初始化，确保后续 import 链路里的 logger 都有 handler
from app.logging_config import setup_logging

setup_logging()

from app.config import CORS_ORIGINS
from app.api.routes import router
from app.api.history import history_manager
from app.services.task_manager import task_manager
from app.services.offload import shutdown as offload_shutdown
from app.services import cleanup

app = FastAPI(title="万能视频下载 API", version="1.0.0")

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)

# 任务完成回调：写入历史
task_manager.set_on_complete(history_manager.add)


@app.on_event("startup")
async def _start_cleanup():
    """启动下载目录自动清理（超时 + 容量上限），防止磁盘被下载文件撑爆。"""
    cleanup.start()


@app.on_event("shutdown")
async def _reap_pools():
    """退出 / 热重载时主动回收线程池，避免卡死的阻塞调用拖住重启。"""
    cleanup.stop()
    offload_shutdown()
    task_manager.shutdown()


@app.get("/")
async def root():
    return {"message": "万能视频下载 API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}
