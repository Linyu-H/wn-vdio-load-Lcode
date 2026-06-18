"""VIP 源健康探测 + 熔断。

核心问题：跨域 iframe 播放成败前端读不到，无法纯前端"失败自动切下一个"。
本模块在后端并发探测各源对目标链接的可达性/有效内容，给出按健康度排序的源列表，
前端据此自动播放第一个健康源；失败累计触发熔断，冷却期内跳过坏源。
"""
from __future__ import annotations

import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# 熔断参数
_FAIL_THRESHOLD = 3        # 连续失败达到此数即熔断
_COOLDOWN_SEC = 180        # 熔断冷却时长
_PROBE_TIMEOUT = 6         # 单源探测超时

# Cloudflare / 拦截页特征（命中视为不可用）
_BLOCK_HINTS = ("cloudflare", "attention required", "access denied", "403 forbidden", "captcha")

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


class _BreakerState:
    """单个源的熔断状态。"""
    __slots__ = ("fails", "opened_at")

    def __init__(self):
        self.fails = 0
        self.opened_at = 0.0

    def is_open(self) -> bool:
        if self.opened_at == 0.0:
            return False
        if time.time() - self.opened_at >= _COOLDOWN_SEC:
            # 冷却结束，半开：清零让其再试
            self.fails = 0
            self.opened_at = 0.0
            return False
        return True

    def record_success(self):
        self.fails = 0
        self.opened_at = 0.0

    def record_failure(self):
        self.fails += 1
        if self.fails >= _FAIL_THRESHOLD:
            self.opened_at = time.time()


class SourceHealth:
    def __init__(self):
        self._breakers: dict[str, _BreakerState] = {}
        self._lock = threading.Lock()

    def _breaker(self, source_id: str) -> _BreakerState:
        with self._lock:
            if source_id not in self._breakers:
                self._breakers[source_id] = _BreakerState()
            return self._breakers[source_id]

    def _probe_one(self, source: dict, target_url: str) -> dict:
        """探测单个源对目标链接的健康度。返回带 health 字段的源副本。"""
        sid = source["id"]
        breaker = self._breaker(sid)
        result = dict(source)
        result["preview_url"] = source["url"] + urllib.parse.quote(target_url, safe="")

        if breaker.is_open():
            result["health"] = "circuit_open"
            result["healthy"] = False
            return result

        ok, reason = self._http_probe(result["preview_url"])
        if ok:
            breaker.record_success()
            result["health"] = "ok"
            result["healthy"] = True
        else:
            breaker.record_failure()
            result["health"] = reason
            result["healthy"] = False
        return result

    @staticmethod
    def _http_probe(preview_url: str) -> tuple[bool, str]:
        """HTTP 探测：连得通、非拦截页、有内容即视为健康。"""
        req = urllib.request.Request(preview_url, headers={"User-Agent": _UA})
        try:
            with urllib.request.urlopen(req, timeout=_PROBE_TIMEOUT) as resp:
                status = resp.status
                body = resp.read(8192).decode("utf-8", errors="ignore").lower()
        except urllib.error.HTTPError as e:
            return False, f"http_{e.code}"
        except Exception:
            return False, "unreachable"

        if status >= 400:
            return False, f"http_{status}"
        if any(hint in body for hint in _BLOCK_HINTS):
            return False, "blocked"
        if len(body) < 80:
            return False, "empty"
        return True, "ok"

    def rank(self, sources: list[dict], target_url: str) -> list[dict]:
        """并发探测全部源，返回健康源在前的有序列表。"""
        if not sources:
            return []
        probed: list[dict] = []
        with ThreadPoolExecutor(max_workers=min(8, len(sources))) as pool:
            futures = {pool.submit(self._probe_one, s, target_url): s for s in sources}
            for fut in as_completed(futures):
                try:
                    probed.append(fut.result())
                except Exception:
                    src = futures[fut]
                    bad = dict(src)
                    bad["health"] = "error"
                    bad["healthy"] = False
                    bad["preview_url"] = src["url"] + urllib.parse.quote(target_url, safe="")
                    probed.append(bad)

        # 保持原始 order，健康的排前面
        order_map = {s["id"]: idx for idx, s in enumerate(sources)}
        probed.sort(key=lambda s: (not s.get("healthy", False), order_map.get(s["id"], 999)))
        return probed

    def report_failure(self, source_id: str):
        """前端反馈某源播放失败时调用，累计熔断。"""
        self._breaker(source_id).record_failure()


# 全局单例
source_health = SourceHealth()
