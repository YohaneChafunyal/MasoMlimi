"""Security helpers for the MasoMlimi API.

Secure by default:
  * Expert/admin endpoints need X-API-Key. If MASOMLIMI_API_KEY is unset they are DENIED
    (set MASOMLIMI_ALLOW_OPEN=1 only on a developer laptop).
  * Constant-time key compare, failed-attempt lockout, per-route rate limits.
  * Strict id/file validation, magic-byte sniffing, safe filenames.
  * Optional at-rest encryption (MASOMLIMI_DATA_KEY) for chat history.
  * HMAC signature for content packs (MASOMLIMI_PACK_SECRET). Launch gate: move to asymmetric signing.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

DEVICE_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
VOICE_RE = re.compile(r"^[a-f0-9]{32}\.(m4a|webm|wav|ogg|mp4|aac)$")
LANG_RE = re.compile(r"^(en|ny|fr|sw|pt)$")
PHONE_RE = re.compile(r"^\+[1-9][0-9]{6,14}$")


def api_key() -> str:
    return (os.environ.get("MASOMLIMI_API_KEY") or "").strip()


def open_mode() -> bool:
    return os.environ.get("MASOMLIMI_ALLOW_OPEN", "") == "1"


def key_ok(provided: Optional[str]) -> bool:
    expected = api_key()
    if not expected:
        return open_mode()
    return hmac.compare_digest((provided or "").strip().encode(), expected.encode())


# kept for compatibility with older code
def require_api_key(header_value: Optional[str]) -> bool:
    return key_ok(header_value)


def _pack_secret() -> bytes:
    s = os.environ.get("MASOMLIMI_PACK_SECRET") or os.environ.get("MASOMLIMI_API_KEY") or "dev-only-change-me"
    return hashlib.sha256(s.encode()).digest()


def sign_payload(payload: str) -> str:
    return hmac.new(_pack_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(payload: str, signature: str) -> bool:
    return bool(signature) and hmac.compare_digest(sign_payload(payload), signature.strip())


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_device_id(device_id: str) -> str:
    salt = (os.environ.get("MASOMLIMI_PRIVACY_SALT") or "masomlimi-pilot").encode()
    return hashlib.sha256(salt + (device_id or "").encode()).hexdigest()[:16]


# ---- at-rest encryption (optional) -------------------------------------------------------------
def _fernet():
    key = (os.environ.get("MASOMLIMI_DATA_KEY") or "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        salt = (os.environ.get("MASOMLIMI_DATA_SALT") or "masomlimi-data").encode()
        raw = hashlib.pbkdf2_hmac("sha256", key.encode(), salt, 200_000, 32)
        return Fernet(base64.urlsafe_b64encode(raw))
    except Exception:
        return None


def encrypt_blob(text: str) -> str:
    f = _fernet()
    return ("enc:" + f.encrypt(text.encode()).decode()) if f else text


def decrypt_blob(text: str) -> str:
    if not text.startswith("enc:"):
        return text
    f = _fernet()
    if not f:
        raise ValueError("data is encrypted but MASOMLIMI_DATA_KEY is not set")
    return f.decrypt(text[4:].encode()).decode()


# ---- rate limiting -----------------------------------------------------------------------------
class RateLimiter:
    def __init__(self) -> None:
        self.h: Dict[str, Deque[float]] = defaultdict(deque)
        self._last_gc = time.monotonic()

    def hit(self, key: str, limit: int, window: float) -> bool:
        now = time.monotonic()
        if now - self._last_gc > 300:
            self.h = defaultdict(deque, {k: v for k, v in self.h.items() if v and now - v[-1] < 600})
            self._last_gc = now
        q = self.h[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def count(self, key: str, window: float) -> int:
        now = time.monotonic()
        q = self.h.get(key)
        return sum(1 for t in q if now - t <= window) if q else 0


# ---- files -------------------------------------------------------------------------------------
def safe_filename(name: str) -> str:
    base = os.path.basename((name or "file").replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "file"
    return base[:80]


def sniff_document(data: bytes, filename: str) -> Optional[str]:
    """Return kind for allowed expert uploads, else None. Never trust the extension alone."""
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    if data[:4] == b"%PDF":
        return "pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"GIF8":
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:4] == b"PK\x03\x04" and ext == "docx":
        return "docx"
    if ext == "txt":
        try:
            data[:20000].decode("utf-8")
            return "txt"
        except UnicodeDecodeError:
            return None
    return None


def sniff_image(data: bytes) -> Optional[str]:
    k = sniff_document(data, "x.bin")
    return k if k in ("png", "jpg", "webp") else None


def sniff_audio(data: bytes) -> Optional[str]:
    if data[4:8] == b"ftyp":
        return "m4a"
    if data[:4] == b"\x1aE\xdf\xa3":
        return "webm"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:2] in (b"\xff\xf1", b"\xff\xf9"):
        return "aac"
    return None
