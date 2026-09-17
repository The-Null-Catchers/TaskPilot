from uuid import uuid4
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_roundtrip():
    encoded = hash_password("a-strong-password")
    assert encoded != "a-strong-password"
    assert verify_password("a-strong-password", encoded)
    assert not verify_password("wrong-password", encoded)


def test_access_token_roundtrip():
    user_id = uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id
