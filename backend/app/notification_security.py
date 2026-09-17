import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def target_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fernet() -> Fernet:
    material = settings.notification_secret or settings.jwt_secret
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_text(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Notification subscription could not be decrypted") from exc


def encrypt_json(value: dict) -> str:
    if not value:
        return ""
    return encrypt_text(json.dumps(value, separators=(",", ":"), sort_keys=True))


def decrypt_json(value: str) -> dict:
    if not value:
        return {}
    decoded = json.loads(decrypt_text(value))
    return decoded if isinstance(decoded, dict) else {}
