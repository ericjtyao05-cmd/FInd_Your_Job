from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256

from cryptography.fernet import Fernet


def build_fernet(secret: str) -> Fernet:
    digest = sha256(secret.encode("utf-8")).digest()
    return Fernet(urlsafe_b64encode(digest))


def encrypt_secret(secret: str, encryption_key: str) -> str:
    return build_fernet(encryption_key).encrypt(secret.encode("utf-8")).decode("utf-8")

