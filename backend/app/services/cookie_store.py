"""多平台 Cookie 存储：管理员可在管理端为各平台粘贴 cookie，解锁登录内容/高清。

设计要点：
- 每个平台一份 Netscape 格式 cookies.txt，存放在 cookies/ 目录，yt-dlp 直接读取。
- 管理员粘贴的内容既支持**浏览器扩展导出的 JSON 数组**（如 "Get cookies.txt"/EditThisCookie），
  也支持**标准 Netscape cookies.txt 文本**，后端自动识别并统一转成 Netscape 存盘。
- 很多平台无需 cookie 即可下载，因此 cookie 是「可选增强」：没有就走匿名解析。
- 不在任何接口里回显 cookie 明文，只返回条数 / 更新时间等元信息（避免泄露登录态）。

首次启动若检测到旧版单文件 youtube_cookies.txt，自动迁移为 youtube 平台的 cookie。
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from app.config import BASE_DIR, YT_COOKIES_FILE

COOKIES_DIR = Path(BASE_DIR / "cookies")
_META_FILE = COOKIES_DIR / "_meta.json"

# 管理端下拉用的已知平台（platform_id -> 展示名）。与 platform.py 对齐，
# 但只列「带 cookie 才更好用」的主流平台；未列出的平台也允许手动填 id。
KNOWN_PLATFORMS = [
    {"id": "youtube", "name": "YouTube"},
    {"id": "bilibili", "name": "哔哩哔哩"},
    {"id": "douyin", "name": "抖音"},
    {"id": "tiktok", "name": "TikTok"},
    {"id": "twitter", "name": "Twitter / X"},
    {"id": "instagram", "name": "Instagram"},
    {"id": "facebook", "name": "Facebook"},
    {"id": "weibo", "name": "微博"},
    {"id": "xiaohongshu", "name": "小红书"},
    {"id": "iqiyi", "name": "爱奇艺"},
    {"id": "youku", "name": "优酷"},
    {"id": "mgtv", "name": "芒果TV"},
]

_NETSCAPE_HEADER = "# Netscape HTTP Cookie File\n# 由管理端写入，供 yt-dlp 使用\n\n"


def _platform_name(platform: str) -> str:
    for p in KNOWN_PLATFORMS:
        if p["id"] == platform:
            return p["name"]
    return platform


def _json_cookies_to_netscape(cookies: list[dict]) -> tuple[str, int]:
    """浏览器扩展导出的 JSON 数组 -> Netscape 文本。返回 (文本, 条数)。"""
    lines = [_NETSCAPE_HEADER.rstrip("\n")]
    count = 0
    for c in cookies:
        if not isinstance(c, dict):
            continue
        domain = c.get("domain")
        name = c.get("name")
        if not domain or name is None:
            continue
        flag = "TRUE" if str(domain).startswith(".") else "FALSE"
        path = c.get("path") or "/"
        secure = "TRUE" if c.get("secure") else "FALSE"
        # 浏览器导出的过期时间字段名不一，做个兼容；会话 cookie 给 0
        exp = c.get("expirationDate") or c.get("expires") or c.get("expiry") or 0
        try:
            exp = int(float(exp))
        except (TypeError, ValueError):
            exp = 0
        value = c.get("value", "")
        lines.append("\t".join([str(domain), flag, str(path), secure, str(exp), str(name), str(value)]))
        count += 1
    return "\n".join(lines) + "\n", count


def _count_netscape_cookies(text: str) -> int:
    """统计 Netscape 文本里的有效 cookie 行（跳过注释/空行）。"""
    count = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "\t" in line and len(line.split("\t")) >= 7:
            count += 1
    return count


def _normalize(raw: str) -> tuple[str, int]:
    """把管理员粘贴的任意支持格式统一成 (Netscape文本, cookie条数)。

    自动识别：以 '[' 或 '{' 开头视为 JSON；否则按 Netscape 文本处理。
    解析失败或 0 条则抛 ValueError。
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("内容为空")

    if text[0] in "[{":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败：{e}") from e
        if isinstance(data, dict):
            # 容错：有的导出是 {"cookies": [...]}
            data = data.get("cookies") if isinstance(data.get("cookies"), list) else [data]
        if not isinstance(data, list):
            raise ValueError("JSON 顶层应为 cookie 数组")
        netscape, count = _json_cookies_to_netscape(data)
        if count == 0:
            raise ValueError("未从 JSON 中解析到任何有效 cookie")
        return netscape, count

    # 当作 Netscape 文本
    count = _count_netscape_cookies(text)
    if count == 0:
        raise ValueError("未识别到有效 cookie 行（应为制表符分隔的 Netscape 格式）")
    body = text if text.startswith("#") else _NETSCAPE_HEADER + text
    if not body.endswith("\n"):
        body += "\n"
    return body, count


class CookieStore:
    def __init__(self, cookies_dir: Path | None = None):
        self._dir = Path(cookies_dir) if cookies_dir else COOKIES_DIR
        self._meta_file = self._dir / "_meta.json"
        self._lock = threading.RLock()
        self._meta: dict[str, dict] = {}
        self._dir.mkdir(parents=True, exist_ok=True)
        self._load()
        self._migrate_legacy()

    # ── 内部读写 ──────────────────────────────────────────────

    def _load(self):
        try:
            with open(self._meta_file, encoding="utf-8") as f:
                self._meta = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._meta = {}

    def _save_meta(self):
        with open(self._meta_file, "w", encoding="utf-8") as f:
            json.dump(self._meta, f, ensure_ascii=False, indent=2)

    def _file_for(self, platform: str) -> Path:
        return self._dir / f"{platform}.txt"

    def _migrate_legacy(self):
        """旧版单文件 youtube_cookies.txt -> youtube 平台 cookie（仅首次）。"""
        with self._lock:
            if "youtube" in self._meta:
                return
            legacy = Path(YT_COOKIES_FILE)
            if not legacy.exists():
                return
            try:
                text = legacy.read_text(encoding="utf-8", errors="ignore")
                body, count = _normalize(text)
            except (OSError, ValueError):
                return
            if count == 0:
                return
            self._file_for("youtube").write_text(body, encoding="utf-8")
            self._meta["youtube"] = {
                "platform": "youtube",
                "count": count,
                "enabled": True,
                "updated_at": time.time(),
            }
            self._save_meta()

    # ── 公开接口 ──────────────────────────────────────────────

    def path_for(self, platform: str) -> str | None:
        """返回该平台启用中的 cookie 文件绝对路径；无则 None（走匿名）。"""
        if not platform:
            return None
        with self._lock:
            meta = self._meta.get(platform)
            if not meta or not meta.get("enabled", True):
                return None
            fp = self._file_for(platform)
            return str(fp) if fp.exists() else None

    def has(self, platform: str) -> bool:
        return self.path_for(platform) is not None

    def list_all(self) -> list[dict]:
        """所有平台 cookie 的状态元信息（不含明文），合并已知平台清单。"""
        with self._lock:
            saved = {p: dict(m) for p, m in self._meta.items()}
        result = []
        seen = set()
        for known in KNOWN_PLATFORMS:
            pid = known["id"]
            seen.add(pid)
            meta = saved.get(pid)
            result.append({
                "platform": pid,
                "name": known["name"],
                "configured": bool(meta),
                "count": meta.get("count", 0) if meta else 0,
                "enabled": meta.get("enabled", True) if meta else False,
                "updated_at": meta.get("updated_at") if meta else None,
            })
        # 用户自定义的、不在已知清单里的平台也带上
        for pid, meta in saved.items():
            if pid in seen:
                continue
            result.append({
                "platform": pid,
                "name": _platform_name(pid),
                "configured": True,
                "count": meta.get("count", 0),
                "enabled": meta.get("enabled", True),
                "updated_at": meta.get("updated_at"),
            })
        return result

    def save(self, platform: str, raw: str) -> dict:
        """保存某平台 cookie（JSON 或 Netscape 自动识别）。返回元信息。"""
        platform = (platform or "").strip().lower()
        if not platform:
            raise ValueError("平台标识不能为空")
        body, count = _normalize(raw)
        with self._lock:
            self._file_for(platform).write_text(body, encoding="utf-8")
            self._meta[platform] = {
                "platform": platform,
                "count": count,
                "enabled": True,
                "updated_at": time.time(),
            }
            self._save_meta()
            return dict(self._meta[platform]) | {"name": _platform_name(platform)}

    def set_enabled(self, platform: str, enabled: bool) -> dict | None:
        with self._lock:
            meta = self._meta.get(platform)
            if not meta:
                return None
            meta["enabled"] = bool(enabled)
            self._save_meta()
            return dict(meta) | {"name": _platform_name(platform)}

    def delete(self, platform: str) -> bool:
        with self._lock:
            if platform not in self._meta:
                return False
            self._meta.pop(platform, None)
            self._save_meta()
            fp = self._file_for(platform)
            if fp.exists():
                fp.unlink()
            return True


# 全局单例
cookie_store = CookieStore()
