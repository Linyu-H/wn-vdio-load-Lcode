"""FastAPI 路由定义。"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.config import DOWNLOAD_DIR
from app.services import downloader
from app.services.platform import is_valid_url
from app.services.vip_parser import build_vip_info, is_vip_supported_url, get_vip_sources_for_url
from app.services.task_manager import task_manager
from app.api.history import history_manager
from app.services.auth import auth_manager, verify_token
from app.services.source_store import source_store
from app.services.source_health import source_health
from app.services.episodes import get_episodes

router = APIRouter(prefix="/api")
logger = logging.getLogger("vdio.api")


# ──────────────────────────────────────────────────────────────
#  鉴权依赖
# ──────────────────────────────────────────────────────────────

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, detail="未登录")
    payload = verify_token(authorization[7:])
    if not payload:
        raise HTTPException(401, detail="登录已失效，请重新登录")
    return payload


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, detail="需要管理员权限")
    return user


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


# ──────────────────────────────────────────────────────────────
#  账号系统
# ──────────────────────────────────────────────────────────────

@router.post("/auth/register")
async def register(username: str = Body(...), password: str = Body(...)):
    try:
        user = auth_manager.register(username, password)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return {"code": 0, "data": user}


@router.post("/auth/login")
async def login(username: str = Body(...), password: str = Body(...)):
    try:
        data = auth_manager.login(username, password)
    except ValueError as e:
        raise HTTPException(401, detail=str(e))
    return {"code": 0, "data": data}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {"code": 0, "data": user}


# ──────────────────────────────────────────────────────────────
#  VIP 源自动解析（健康探测 + 熔断排序）
# ──────────────────────────────────────────────────────────────

@router.post("/vip/resolve")
async def vip_resolve(url: str = Body(..., embed=True)):
    """返回当前链接的健康 VIP 源有序列表（健康的排前面，供前端自动播放）。"""
    if not is_valid_url(url):
        raise HTTPException(400, detail="链接格式无效")
    sources = get_vip_sources_for_url(url)
    if not sources:
        return {"code": 0, "data": {"sources": [], "best": None}}
    ranked = await asyncio.to_thread(source_health.rank, sources, url)
    best = next((s for s in ranked if s.get("healthy")), ranked[0] if ranked else None)
    return {"code": 0, "data": {"sources": ranked, "best": best}}


@router.post("/vip/report-failure")
async def vip_report_failure(source_id: str = Body(..., embed=True)):
    """前端反馈某源播放失败，累计熔断。"""
    source_health.report_failure(source_id)
    return {"code": 0, "msg": "已记录"}


# ──────────────────────────────────────────────────────────────
#  上下集导航
# ──────────────────────────────────────────────────────────────

@router.get("/episodes")
async def episodes(url: str = Query(...)):
    if not is_valid_url(url):
        raise HTTPException(400, detail="链接格式无效")
    data = await asyncio.to_thread(get_episodes, url)
    return {"code": 0, "data": data}


# ──────────────────────────────────────────────────────────────
#  管理端：VIP 源 CRUD（需 admin）
# ──────────────────────────────────────────────────────────────

@router.get("/admin/sources")
async def admin_list_sources(_: dict = Depends(require_admin)):
    return {"code": 0, "data": source_store.list_all()}


@router.post("/admin/sources")
async def admin_add_source(
    name: str = Body(...),
    url: str = Body(...),
    enabled: bool = Body(True),
    _: dict = Depends(require_admin),
):
    if not url.strip():
        raise HTTPException(400, detail="解析源 URL 不能为空")
    source = source_store.add(name, url, enabled)
    return {"code": 0, "data": source}


@router.put("/admin/sources/{source_id}")
async def admin_update_source(
    source_id: str,
    name: Optional[str] = Body(None),
    url: Optional[str] = Body(None),
    enabled: Optional[bool] = Body(None),
    order: Optional[int] = Body(None),
    _: dict = Depends(require_admin),
):
    updated = source_store.update(source_id, name=name, url=url, enabled=enabled, order=order)
    if not updated:
        raise HTTPException(404, detail="解析源不存在")
    return {"code": 0, "data": updated}


@router.delete("/admin/sources/{source_id}")
async def admin_delete_source(source_id: str, _: dict = Depends(require_admin)):
    if not source_store.delete(source_id):
        raise HTTPException(404, detail="解析源不存在")
    return {"code": 0, "msg": "已删除"}
