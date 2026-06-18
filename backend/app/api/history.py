"""历史记录管理：JSON 文件持久化，线程安全。

提供增、删、查、清空能力，由 task_manager 完成回调触发写入。
"""
from __future__ import annotations

import json
import threading
import time
from typing import Optional

from app.config import HISTORY_FILE


class HistoryManager:
    def __init__(self, file_path: str | None = None):
        self._path = file_path or str(HISTORY_FILE)
        self._lock = threading.Lock()
        self._records: list[dict] = []
        self._load()

    # ── 内部读写 ──────────────────────────────────────────────

    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as f:
                self._records = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._records = []

    def _save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._records, f, ensure_ascii=False, indent=2)

    # ── 公开接口 ──────────────────────────────────────────────

    def add(self, record: dict):
        """新增一条历史记录（下载完成时调用）。"""
        record["downloaded_at"] = time.time()
        with self._lock:
            self._records.insert(0, record)
            if len(self._records) > 500:          # 最多保留 500 条
                self._records.pop()
            self._save()

    def list(self, limit: int = 50) -> list[dict]:
        """返回最近 limit 条记录。"""
        with self._lock:
            return self._records[:limit]

    def delete(self, task_id: str) -> bool:
        """按 task_id 删除单条。返回是否存在并删除。"""
        with self._lock:
            before = len(self._records)
            self._records = [r for r in self._records if r.get("id") != task_id]
            removed = len(self._records) < before
            if removed:
                self._save()
            return removed

    def clear(self):
        """清空全部记录。"""
        with self._lock:
            self._records.clear()
            self._save()


# 全局单例
history_manager = HistoryManager()
