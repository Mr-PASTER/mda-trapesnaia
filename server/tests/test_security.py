from app.core.security import (
    hash_fingerprint,
    hash_password,
    hash_token,
    new_token,
    verify_password,
)


def test_password_roundtrip():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password(h, "secret123") is True
    assert verify_password(h, "wrong") is False


def test_token_is_random_and_hashed_deterministically():
    t1, t2 = new_token(), new_token()
    assert t1 != t2
    assert hash_token(t1) == hash_token(t1)
    assert len(hash_token(t1)) == 64


def test_fingerprint_hash_stable():
    assert hash_fingerprint("abc") == hash_fingerprint("abc")
    assert hash_fingerprint("abc") != hash_fingerprint("abd")
