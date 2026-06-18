"""FastAPI 路由定义。"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.config import DOWNLOAD_DIR
from app.services import downloader
from app.services.platform import is_valid_url
from app.services.vip_parser import build_vip_info, is_vip_supported_url
from app.services.task_manager import task_manager
from app.api.history import history_manager

router = APIRouter(prefix="/api")
logger = logging.getLogger("vdio.api")


# ──────────────────────────────────────────────────────────────
#  T2.1  解析视频信息
# ──────────────────────────────────────────────────────────────

@router.post("/info")
async def info(
    url: str = Body(..., embed=True),
    force_vip: bool = Body(False),
):
    logger.info("parse_info start force_vip=%s url=%s", force_vip, url)
    if not is_valid_url(url):
        logger.warning("parse_info invalid_url url=%s", url)
        raise HTTPException(400, detail="链接格式无效，请输入 http(s):// 开头的有效 URL")

    if force_vip:
        if not is_vip_supported_url(url):
            logger.warning("parse_info force_vip unsupported url=%s", url)
            raise HTTPException(400, detail="当前链接不支持 VIP 解析模式")
        data = build_vip_info(url)
        logger.info(
            "parse_info force_vip built url=%s preview=%s sources=%s",
            url,
            bool(data.get("preview_url")),
            len(data.get("vip_parse_sources") or []),
        )
        if not data.get("preview_url"):
            logger.error("parse_info force_vip no_preview url=%s", url)
            raise HTTPException(400, detail="VIP 解析源不可用，请稍后重试或切换链接")
        return {"code": 0, "data": data}

    try:
        data = downloader.extract_info(url)
        has_embed = downloader.has_embeddable_preview(url, data)
        logger.info(
            "parse_info normal ok url=%s platform=%s preview=%s has_embed=%s vip_supported=%s",
            url,
            data.get("platform"),
            data.get("preview_url"),
            has_embed,
            is_vip_supported_url(url),
        )
        if is_vip_supported_url(url) and not has_embed:
            logger.info("parse_info normal no_embed fallback_vip url=%s", url)
            return {"code": 0, "data": build_vip_info(url)}
        # 能正常解析且有官方可嵌入播放器（如 B 站普通 BV 视频）时，
        # 清除 VIP 解析标记，避免前端误用第三方 jx 解析源导致无法播放。
        if has_embed:
            data["vip_supported"] = False
            data["vip_preview_url"] = None
            data["vip_parse_sources"] = []
    except Exception as e:
        logger.exception("parse_info normal failed url=%s", url)
        if is_vip_supported_url(url):
            logger.info("parse_info exception fallback_vip url=%s", url)
            return {"code": 0, "data": build_vip_info(url, str(e)[:200])}
        raise HTTPException(400, detail=f"解析失败: {str(e)[:200]}") from e

    return {"code": 0, "data": data}


# ──────────────────────────────────────────────────────────────
#  T2.2  创建下载任务
# ──────────────────────────────────────────────────────────────

@router.post("/download")
async def create_download(
    url: str = Body(...),
    quality: str = Body("1080"),
    audio_only: bool = Body(False),
    vip_source_id: Optional[str] = Body(None),
):
    if not is_valid_url(url):
        raise HTTPException(400, detail="链接格式无效")

    task = task_manager.create(url, quality, audio_only, vip_source_id)
    return {"code": 0, "data": {"task_id": task.id}}


# ──────────────────────────────────────────────────────────────
#  T2.3  WebSocket 实时进度推送
# ──────────────────────────────────────────────────────────────

@router.websocket("/ws/{task_id}")
async def ws_progress(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        while True:
            task = task_manager.get(task_id)
            if task is None:
                await websocket.send_json({"code": -1, "msg": "任务不存在"})
                break
            await websocket.send_json({"code": 0, "data": task.to_dict()})
            if task.status in ("completed", "error"):
                break
            await asyncio.sleep(0.3)          # 300ms 轮询间隔
    except WebSocketDisconnect:
        pass


# ──────────────────────────────────────────────────────────────
#  T2.4  下载已完成文件
# ──────────────────────────────────────────────────────────────

@router.get("/file/{task_id}")
async def download_file(task_id: str):
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在")
    if task.status != "completed" or not task.filepath:
        raise HTTPException(400, detail="文件尚未下载完成")

    fp = Path(task.filepath)
    if not fp.exists():
        raise HTTPException(404, detail="文件已被清理或不存在")

    return FileResponse(
        path=str(fp),
        filename=task.filename or fp.name,
        media_type="application/octet-stream",
    )


# ──────────────────────────────────────────────────────────────
#  T2.5  历史记录管理
# ──────────────────────────────────────────────────────────────

@router.get("/history")
async def list_history(limit: int = Query(50, ge=1, le=200)):
    return {"code": 0, "data": history_manager.list(limit)}


@router.delete("/history/{task_id}")
async def delete_history(task_id: str):
    ok = history_manager.delete(task_id)
    if not ok:
        raise HTTPException(404, detail="记录不存在")
    return {"code": 0, "msg": "已删除"}


@router.delete("/history")
async def clear_history():
    history_manager.clear()
    return {"code": 0, "msg": "历史记录已清空"}
