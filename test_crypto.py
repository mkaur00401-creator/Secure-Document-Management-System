import os
import sys
import sqlite3
import hashlib
import hmac

print("Testing database and crypto...")

def hash_password(password: str, salt: str = None):
    if salt is None:
        salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100_000
    ).hex()
    return pwd_hash, salt

def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    pwd_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(pwd_hash, expected_hash)

p_hash, p_salt = hash_password("secret123")
assert verify_password("secret123", p_salt, p_hash)
assert not verify_password("wrong", p_salt, p_hash)
print("Password hashing test passed!")
