from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Dict

try:
    import bcrypt  # type: ignore
except ImportError:  # pragma: no cover - dependency declared in requirements.txt
    bcrypt = None  # type: ignore[assignment]

from app.config import Settings

JWT_ALGORITHM = "HS256"
BCRYPT_ROUNDS = 12
# bcrypt only reads the first 72 bytes of a password.
BCRYPT_MAX_PASSWORD_BYTES = 72

# A real bcrypt hash of a value nobody can supply, used to burn the same amount
# of CPU when the username does not exist. Without it, "unknown user" returns
# noticeably faster than "wrong password" and becomes an enumeration oracle.
DUMMY_PASSWORD_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEe.6uCiVUpvBnFRvzPRXBUZfeRTpEmxD1O"  # nosec B105


def hash_password(password: str) -> str:
    if not isinstance(password, str):
        raise TypeError("password phai la chuoi.")
    if bcrypt is None:
        raise RuntimeError(
            "Thu vien 'bcrypt' chua duoc cai dat. Chay 'pip install bcrypt' truoc."
        )
    if len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Mat khau vuot qua {BCRYPT_MAX_PASSWORD_BYTES} byte — bcrypt se cat bot am tham."
        )
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def _legacy_sha256_hash(password: str) -> str:
    encoded = password.encode("utf-16le")
    return hashlib.sha256(encoded).hexdigest().upper()


def _is_bcrypt_hash(stored: str) -> bool:
    return stored.startswith(("$2a$", "$2b$", "$2y$"))


def verify_password(password: str, password_hash: str) -> bool:
    stored = str(password_hash or "").strip()
    if not stored:
        return False
    if _is_bcrypt_hash(stored):
        if bcrypt is None:
            return False
        try:
            return bcrypt.checkpw(
                password.encode("utf-8")[:BCRYPT_MAX_PASSWORD_BYTES], stored.encode("utf-8")
            )
        except (ValueError, TypeError):
            return False
    candidate = _legacy_sha256_hash(password)
    return hmac.compare_digest(candidate, stored.upper())


def needs_rehash(password_hash: str) -> bool:
    """Return True when the stored hash is a legacy format that should be upgraded."""
    stored = str(password_hash or "").strip()
    return bool(stored) and not _is_bcrypt_hash(stored)


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _b64url_decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode((payload + padding).encode("ascii"))


@dataclass(frozen=True)
class AuthToken:
    token: str
    expires_at: int


def create_access_token(
    *,
    subject: str,
    claims: Dict[str, Any],
    settings: Settings,
) -> AuthToken:
    issued_at = int(time.time())
    expires_at = issued_at + settings.auth_token_ttl_minutes * 60
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": subject,
        "iat": issued_at,
        "exp": expires_at,
        **claims,
    }
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(
        settings.auth_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    encoded_signature = _b64url_encode(signature)
    return AuthToken(
        token=f"{encoded_header}.{encoded_payload}.{encoded_signature}",
        expires_at=expires_at,
    )


def decode_access_token(token: str, settings: Settings) -> Dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise ValueError("Token khong hop le.") from exc

    try:
        header = json.loads(_b64url_decode(encoded_header).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Header token khong hop le.") from exc

    if not isinstance(header, dict) or header.get("alg") != JWT_ALGORITHM:
        raise ValueError("Thuat toan token khong duoc ho tro.")

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected_signature = hmac.new(
        settings.auth_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    try:
        actual_signature = _b64url_decode(encoded_signature)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("Chu ky token khong hop le.") from exc
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise ValueError("Chu ky token khong hop le.")

    try:
        payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Payload token khong hop le.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Payload token khong hop le.")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token da het han.")
    return payload
