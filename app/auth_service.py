import base64
import json
import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from app.config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import get_db

# Helper functions for URL-safe base64 encoding/decoding without padding
def base64url_encode(data: bytes) -> str:
    """Encodes bytes into a URL-safe Base64 string without trailing '=' padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def base64url_decode(data: str) -> bytes:
    """Decodes a URL-safe Base64 string with optional restored padding."""
    padding = '=' * (4 - len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)

# Secure password hashing using PBKDF2-HMAC (recommended by OWASP)
def hash_password(password: str) -> str:
    """Hashes a password using PBKDF2-HMAC-SHA256 with a secure salt."""
    salt = os_urandom_salt(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000  # Number of iterations
    )
    return f"{salt.hex()}:{key.hex()}"

def os_urandom_salt(length: int) -> bytes:
    """Generates random bytes using os.urandom."""
    import os
    return os.urandom(length)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against the saved PBKDF2 hash."""
    try:
        salt_hex, key_hex = hashed_password.split(':')
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        
        # Hash the plain password using the same salt and parameters
        key = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt,
            100000
        )
        return hmac.compare_digest(key, expected_key)
    except Exception:
        return False

# Pure Python HMAC-SHA256 JWT Implementation
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token signed with HMAC-SHA256."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Store timestamp as Unix epoch integer
    to_encode.update({"exp": int(expire.timestamp())})
    
    # Build JWT parts
    header = {"alg": "HS256", "typ": "JWT"}
    header_bytes = json.dumps(header, separators=(',', ':')).encode('utf-8')
    payload_bytes = json.dumps(to_encode, separators=(',', ':')).encode('utf-8')
    
    header_b64 = base64url_encode(header_bytes)
    payload_b64 = base64url_encode(payload_bytes)
    
    # Sign JWT
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(
        JWT_SECRET_KEY.encode('utf-8'),
        signing_input,
        hashlib.sha256
    ).digest()
    
    signature_b64 = base64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_access_token(token: str) -> Optional[dict]:
    """Decodes and validates a JWT access token."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
            
        header_b64, payload_b64, signature_b64 = parts
        
        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig_bytes = hmac.new(
            JWT_SECRET_KEY.encode('utf-8'),
            signing_input,
            hashlib.sha256
        ).digest()
        expected_signature_b64 = base64url_encode(expected_sig_bytes)
        
        if not hmac.compare_digest(signature_b64, expected_signature_b64):
            return None
            
        # Parse payload
        payload_bytes = base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        # Check expiration
        exp = payload.get("exp")
        if exp is not None:
            now = datetime.now(timezone.utc).timestamp()
            if now > exp:
                return None  # Token expired
                
        return payload
    except Exception:
        return None

def authenticate_user(token: str) -> Optional[Dict[str, Any]]:
    """Authenticates user profile from token string."""
    payload = decode_access_token(token)
    if not payload:
        return None
        
    username = payload.get("sub")
    if not username:
        return None
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, gemini_key FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if user:
            return {
                "id": user["id"],
                "username": user["username"],
                "gemini_key": user["gemini_key"]
            }
    return None
