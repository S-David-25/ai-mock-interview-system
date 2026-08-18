import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional, Dict, Any
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using PBKDF2-HMAC-SHA256 with a unique random salt.
    Format: pbkdf2_sha256$iterations$salt_hex$hash_hex
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    iterations = 100000
    salt = secrets.token_bytes(16)
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        iterations
    )
    return f"pbkdf2_sha256${iterations}${salt.hex()}${pw_hash.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against the stored PBKDF2 hash.
    Constant-time comparison protects against timing attacks.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        parts = hashed_password.split('$')
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_hash = bytes.fromhex(parts[3])

        actual_hash = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt,
            iterations
        )
        return hmac.compare_digest(actual_hash, expected_hash)
    except Exception:
        return False

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def _base64url_decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode('utf-8'))

def create_access_token(data: Dict[str, Any], expires_delta_minutes: Optional[int] = None) -> str:
    """
    Generates a secure standard JWT token signed with HMAC-SHA256.
    """
    header = {
        "alg": "HS256",
        "typ": "JWT"
    }
    expire_minutes = expires_delta_minutes if expires_delta_minutes is not None else ACCESS_TOKEN_EXPIRE_MINUTES
    now = int(time.time())
    exp = now + (expire_minutes * 60)

    payload = dict(data)
    payload["iat"] = now
    payload["exp"] = exp

    header_bytes = json.dumps(header, separators=(',', ':')).encode('utf-8')
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')

    header_b64 = _base64url_encode(header_bytes)
    payload_b64 = _base64url_encode(payload_bytes)

    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(SECRET_KEY.encode('utf-8'), signing_input, hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and verifies a JWT token. Raises ValueError if invalid or expired.
    """
    if not token or token.count('.') != 2:
        raise ValueError("Invalid token format")

    header_b64, payload_b64, signature_b64 = token.split('.')
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    expected_signature = hmac.new(SECRET_KEY.encode('utf-8'), signing_input, hashlib.sha256).digest()
    actual_signature = _base64url_decode(signature_b64)

    if not hmac.compare_digest(actual_signature, expected_signature):
        raise ValueError("Token signature verification failed")

    payload_json = _base64url_decode(payload_b64).decode('utf-8')
    payload = json.loads(payload_json)

    # Expiration check
    if "exp" in payload and payload["exp"] < int(time.time()):
        raise ValueError("Token has expired")

    return payload
