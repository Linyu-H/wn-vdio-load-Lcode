"""账号系统：JSON 持久化用户 + pbkdf2 密码哈希 + HMAC 签名 token。

零额外依赖（仅标准库 hashlib/hmac/secrets）。公开注册已下线，仅保留管理员账号
用于后台维护；首次启动用环境变量 ADMIN_USERNAME / ADMIN_PASSWORD 种子默认管理员。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

from app.config import BASE_DIR

USERS_FILE = Path(BASE_DIR / "users.json")

# token 签名密钥：环境变量 AUTH_SECRET 优先；否则持久化到 .auth_secret 文件，
# 保证重启后已签发 token 仍有效（管理员不会每次重启都被强制重新登录）。
def _load_secret() -> bytes:
    env = os.getenv("AUTH_SECRET")
    if env:
        return env.encode()
    secret_file = Path(BASE_DIR / ".auth_secret")
    try:
        if secret_file.exists():
            val = secret_file.read_text(encoding="utf-8").strip()
            if val:
                return val.encode()
        val = secrets.token_hex(32)
        secret_file.write_text(val, encoding="utf-8")
        try:
            os.chmod(secret_file, 0o600)
        except OSError:
            pass
        return val.encode()
    except OSError:
        # 文件不可写则退回随机（重启失效，但不致崩溃）
        return secrets.token_hex(32).encode()


_SECRET = _load_secret()
_TOKEN_TTL = int(os.getenv("AUTH_TOKEN_TTL", str(7 * 24 * 3600)))  # 默认 7 天

_PBKDF2_ROUNDS = 120_000


# ── 密码哈希 ──────────────────────────────────────────────────

def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"{salt.hex()}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ── token：payload.base64 + HMAC 签名 ─────────────────────────

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _make_token(username: str, role: str) -> str:
    payload = json.dumps({"u": username, "r": role, "exp": int(time.time()) + _TOKEN_TTL}).encode()
    body = _b64(payload)
    sig = _b64(hmac.new(_SECRET, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str) -> dict | None:
    try:
        body, sig = token.split(".", 1)
        expected = _b64(hmac.new(_SECRET, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64d(body))
        if payload.get("exp", 0) < time.time():
            return None
        return {"username": payload["u"], "role": payload["r"]}
    except Exception:
        return None


# ── 用户存储 ──────────────────────────────────────────────────

class AuthManager:
    def __init__(self, file_path: str | None = None):
        self._path = file_path or str(USERS_FILE)
        self._lock = threading.Lock()
        self._users: dict[str, dict] = {}
        self._load()
        self._seed_admin()

    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as f:
                self._users = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._users = {}

    def _save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._users, f, ensure_ascii=False, indent=2)

    def _seed_admin(self):
        username = os.getenv("ADMIN_USERNAME", "admin")
        password = os.getenv("ADMIN_PASSWORD", "admin123")
        with self._lock:
            if username not in self._users:
                self._users[username] = {
                    "username": username,
                    "password": _hash_password(password),
                    "role": "admin",
                    "created_at": time.time(),
                }
                self._save()

    # ── 公开接口 ──────────────────────────────────────────────
    # 注：公开注册已下线，系统仅保留管理员账号（_seed_admin 种子）用于后台维护。

    def login(self, username: str, password: str) -> dict:
        with self._lock:
            user = self._users.get((username or "").strip())
        if not user or not _verify_password(password or "", user["password"]):
            raise ValueError("用户名或密码错误")
        return {
            "token": _make_token(user["username"], user["role"]),
            "username": user["username"],
            "role": user["role"],
        }

    def get_user(self, username: str) -> dict | None:
        with self._lock:
            user = self._users.get(username)
            return {"username": user["username"], "role": user["role"]} if user else None


# 全局单例
auth_manager = AuthManager()
