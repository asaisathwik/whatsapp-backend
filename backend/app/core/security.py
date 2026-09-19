import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if isinstance(plain_password, str):
        plain_password = plain_password.encode("utf-8")
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_password[:72], hashed_password)

def get_password_hash(password: str) -> str:
    if isinstance(password, str):
        password = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password[:72], salt).decode("utf-8")

def create_access_token(
    subject: Union[str, Any],
    organization_id: Optional[str] = None,
    role: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "org_id": str(organization_id) if organization_id else None,
        "role": role or "AGENT"
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
