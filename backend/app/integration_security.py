import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet

from app.core.config import settings


def new_personal_token() -> str:
    return f"tp_pat_{secrets.token_urlsafe(36)}"


def personal_token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_webhook_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(36)}"


def _fernet() -> Fernet:
    secret = settings.integration_secret or settings.jwt_secret
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def secret_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sign_webhook(secret: str, timestamp: int, body: bytes) -> str:
    payload = str(timestamp).encode() + b"." + body
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"v1={digest}"
