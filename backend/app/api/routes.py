"""FastAPI 路由定义。"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse

from app.config import DOWNLOAD_DIR
from app.services import downloader
from app.services.platform import is_valid_url
from app.services.vip_parser import build_vip_info, is_vip_supported_url, get_vip_sources_for_url
from app.services.task_manager import task_manager
from app.api.history import history_manager
from app.services.auth import auth_manager, verify_token
from app.services.source_store import source_store
from app.services.source_health import source_health
from app.services.cookie_store import cookie_store
from app.services.episodes import get_episodes
from app.services.offload import run_blocking

router = APIRouter(prefix="/api")
logger = logging.getLogger("vdio.api")

# 阻塞型操作的超时上限（秒），到点不再等待，按失败/降级处理，避免请求悬挂。
# YouTube 走 fail-fast：连不上时约 15~20s 内带"配置代理"提示返回，无需等满。
PARSE_TIMEOUT = 45
RESOLVE_TIMEOUT = 40
EPISODES_TIMEOUT = 45


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
        # 阻塞型解析(yt-dlp + 取站点图标)丢到 daemon 线程池，避免卡死事件循环；
        # 超时按失败处理（VIP 站点回退解析源，普通站点返回 504）。
        data = await run_blocking(downloader.extract_info, url, timeout=PARSE_TIMEOUT)
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
        is_timeout = isinstance(e, asyncio.TimeoutError)
        reason = "解析超时，请重试" if is_timeout else (str(e)[:200] or "解析失败")
        if is_vip_supported_url(url):
            logger.info("parse_info exception fallback_vip url=%s", url)
            return {"code": 0, "data": build_vip_info(url, reason)}
        if not is_timeout and downloader.is_unsupported_url_error(e):
            logger.info("parse_info unsupported fallback_webpage url=%s", url)
            return {"code": 0, "data": downloader.build_webpage_info(url, reason)}
        raise HTTPException(504 if is_timeout else 400, detail=f"解析失败: {reason}") from e

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
            await asyncio.sleep(1.0)          # 1s 轮询间隔，降低 WebSocket/CPU 负载
    except WebSocketDisconnect:
        pass


# ──────────────────────────────────────────────────────────────
#  T2.4  下载已完成文件
# ──────────────────────────────────────────────────────────────

@router.get("/file/{task_id}")
async def download_file(
    task_id: str,
    inline: bool = Query(False),
    range_header: Optional[str] = Header(None, alias="Range"),
):
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在")
    if task.status != "completed" or not task.filepath:
        raise HTTPException(400, detail="文件尚未下载完成")

    fp = Path(task.filepath)
    if not fp.exists():
        raise HTTPException(404, detail="文件已被清理或不存在")

    filename = task.filename or fp.name
    media_type = "video/mp4" if fp.suffix.lower() == ".mp4" else "application/octet-stream"

    # 普通下载：保持 FileResponse，让浏览器保存文件名。
    # 页面内播放会带 inline=1，避免 Content-Disposition: attachment 让 video 不渲染。
    if not range_header:
        if inline:
            return FileResponse(path=str(fp), media_type=media_type)
        return FileResponse(
            path=str(fp),
            filename=filename,
            media_type=media_type,
        )

    # 浏览器 video/audio 会发 Range 请求；只返回请求片段，避免整文件读入/传输，
    # 大视频在线播放更顺滑，也更省服务器带宽和内存。
    file_size = fp.stat().st_size
    try:
        range_value = range_header.strip().lower().replace("bytes=", "", 1)
        start_s, end_s = (range_value.split("-", 1) + [""])[:2]
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else min(start + 1024 * 1024 - 1, file_size - 1)
        end = min(end, file_size - 1)
        if start < 0 or start >= file_size or end < start:
            raise ValueError
    except ValueError:
        raise HTTPException(416, detail="Range 不合法")

    chunk_size = 256 * 1024

    def iter_file():
        remaining = end - start + 1
        with open(fp, "rb") as f:
            f.seek(start)
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
        # 不放中文 filename：HTTP header 只能 latin-1，中文会导致 500，video 播放也不需要文件名。
        "Content-Disposition": "inline",
        "Cache-Control": "no-store",
    }
    return StreamingResponse(iter_file(), status_code=206, headers=headers, media_type=media_type)


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

# 公开注册已下线：仅管理员账号（环境变量种子）用于后台维护，无普通用户体系。


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
    try:
        ranked = await run_blocking(source_health.rank, sources, url, timeout=RESOLVE_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("vip_resolve probe timeout url=%s", url)
        ranked = sources  # 探测超时：退回未排序源，至少保证可用
    best = next((s for s in ranked if s.get("healthy")), ranked[0] if ranked else None)
    return {"code": 0, "data": {"sources": ranked, "best": best}}


@router.post("/vip/report-failure")
async def vip_report_failure(source_id: str = Body(..., embed=True)):
    """前端反馈某源播放失败：直接禁用该源，以后解析不再使用（熔断）。"""
    source_health.report_failure(source_id)
    source_store.update(source_id, enabled=False)
    return {"code": 0, "msg": "已禁用该源"}


# ──────────────────────────────────────────────────────────────
#  上下集导航
# ──────────────────────────────────────────────────────────────

@router.get("/episodes")
async def episodes(url: str = Query(...)):
    if not is_valid_url(url):
        raise HTTPException(400, detail="链接格式无效")
    try:
        data = await run_blocking(get_episodes, url, timeout=EPISODES_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("episodes timeout url=%s", url)
        data = {"episodes": [], "current_index": -1}
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


# ──────────────────────────────────────────────────────────────
#  管理端：多平台 Cookie 管理（需 admin）
#  cookie 是可选增强：很多平台无 cookie 也能下载；配置后解锁登录内容/高清。
# ──────────────────────────────────────────────────────────────

@router.get("/admin/cookies")
async def admin_list_cookies(_: dict = Depends(require_admin)):
    """各平台 cookie 状态（仅元信息，不回显明文）。"""
    return {"code": 0, "data": cookie_store.list_all()}


@router.put("/admin/cookies/{platform}")
async def admin_set_cookie(
    platform: str,
    content: str = Body(..., embed=True),
    _: dict = Depends(require_admin),
):
    """保存某平台 cookie。content 支持浏览器扩展导出的 JSON 数组或 Netscape 文本，自动识别。"""
    try:
        meta = cookie_store.save(platform, content)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return {"code": 0, "data": meta}


@router.patch("/admin/cookies/{platform}")
async def admin_toggle_cookie(
    platform: str,
    enabled: bool = Body(..., embed=True),
    _: dict = Depends(require_admin),
):
    meta = cookie_store.set_enabled(platform, enabled)
    if not meta:
        raise HTTPException(404, detail="该平台尚未配置 cookie")
    return {"code": 0, "data": meta}


@router.delete("/admin/cookies/{platform}")
async def admin_delete_cookie(platform: str, _: dict = Depends(require_admin)):
    if not cookie_store.delete(platform):
        raise HTTPException(404, detail="该平台尚未配置 cookie")
    return {"code": 0, "msg": "已清除该平台 cookie"}
