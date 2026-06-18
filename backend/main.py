"""FastAPI 应用主入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.api.routes import router
from app.api.history import history_manager
from app.services.task_manager import task_manager

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


@app.get("/")
async def root():
    return {"message": "万能视频下载 API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}
