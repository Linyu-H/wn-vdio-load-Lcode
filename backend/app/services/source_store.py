"""VIP 解析源存储：JSON 持久化 + 线程安全，支持增删改查 / 启用禁用 / 排序。

替代原先硬编码在 vip_parser.py 的 VIP_PARSE_SOURCES，使管理员可在管理端动态维护源，
无需改源码。首次启动若文件不存在，用内置种子源迁移初始化。
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from app.config import BASE_DIR

SOURCES_FILE = Path(BASE_DIR / "vip_sources.json")

# 内置种子源（首次启动迁移用）
_SEED_SOURCES = [
    {"name": "默认A", "url": "https://json.fongmi.cc/web?url="},
    {"name": "默认B", "url": "https://super.playr.top/?url="},
    {"name": "Node解析", "url": "https://jx.nodenode.dpdns.org/?url="},
    {"name": "CK解析", "url": "https://www.ckplayer.vip/jiexi/?url="},
    {"name": "Player-JY", "url": "https://jx.playerjy.com/?url="},
    {"name": "虾米解析", "url": "https://jx.xmflv.com/?url="},
    {"name": "789解析", "url": "https://jiexi.789jiexi.icu:4433/?url="},
    {"name": "937解析", "url": "https://bfq.937auth.vip?url="},
    {"name": "HLS解析", "url": "https://jx.hls.one/?url="},
    {"name": "极速解析", "url": "https://jx.2s0.cn/player/?url="},
    {"name": "冰豆解析", "url": "https://bd.jx.cn/?url="},
    {"name": "剖元解析", "url": "https://www.pouyun.com/?url="},
    {"name": "973解析", "url": "https://jx.973973.xyz/?url="},
    {"name": "七哥解析", "url": "https://jx.nnxv.cn/tv.php?url="},
    {"name": "playm3u8", "url": "https://www.playm3u8.cn/jiexi.php?url="},
    {"name": "七七云解析", "url": "https://jx.77flv.cc/?url="},
    {"name": "芒果TV1", "url": "https://video.isyour.love/player/getplayer?url="},
    {"name": "M1907", "url": "https://im1907.top/?jx="},
    {"name": "Yparse", "url": "https://jx.yparse.com/index.php?url="},
]


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


class SourceStore:
    def __init__(self, file_path: str | None = None):
        self._path = file_path or str(SOURCES_FILE)
        self._lock = threading.RLock()
        self._sources: list[dict] = []
        self._load()

    # ── 内部读写 ──────────────────────────────────────────────

    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as f:
                self._sources = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._seed()

    def _seed(self):
        now = time.time()
        self._sources = [
            {
                "id": _new_id(),
                "name": s["name"],
                "url": s["url"],
                "enabled": True,
                "order": idx,
                "created_at": now,
            }
            for idx, s in enumerate(_SEED_SOURCES)
        ]
        self._save()

    def _save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._sources, f, ensure_ascii=False, indent=2)

    def _sorted(self, items: list[dict]) -> list[dict]:
        return sorted(items, key=lambda s: (s.get("order", 0), s.get("created_at", 0)))

    # ── 公开接口 ──────────────────────────────────────────────

    def list_all(self) -> list[dict]:
        """全部源（含禁用），按 order 排序——管理端用。"""
        with self._lock:
            return [dict(s) for s in self._sorted(self._sources)]

    def list_enabled(self) -> list[dict]:
        """仅启用的源，按 order 排序——解析时用。"""
        with self._lock:
            return [dict(s) for s in self._sorted(self._sources) if s.get("enabled", True)]

    def get(self, source_id: str) -> dict | None:
        with self._lock:
            for s in self._sources:
                if s["id"] == source_id:
                    return dict(s)
        return None

    def add(self, name: str, url: str, enabled: bool = True) -> dict:
        with self._lock:
            max_order = max((s.get("order", 0) for s in self._sources), default=-1)
            record = {
                "id": _new_id(),
                "name": name.strip() or "未命名源",
                "url": url.strip(),
                "enabled": bool(enabled),
                "order": max_order + 1,
                "created_at": time.time(),
            }
            self._sources.append(record)
            self._save()
            return dict(record)

    def update(self, source_id: str, **fields) -> dict | None:
        allowed = {"name", "url", "enabled", "order"}
        with self._lock:
            for s in self._sources:
                if s["id"] == source_id:
                    for key, val in fields.items():
                        if key in allowed and val is not None:
                            s[key] = val.strip() if isinstance(val, str) else val
                    self._save()
                    return dict(s)
        return None

    def delete(self, source_id: str) -> bool:
        with self._lock:
            before = len(self._sources)
            self._sources = [s for s in self._sources if s["id"] != source_id]
            removed = len(self._sources) < before
            if removed:
                self._save()
            return removed


# 全局单例
source_store = SourceStore()
