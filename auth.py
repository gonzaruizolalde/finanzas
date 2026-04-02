import os
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Cookie
from sqlalchemy.orm import Session

from database import get_db, User

SECRET_KEY  = os.getenv("SECRET_KEY", "cambia-esto-en-produccion-usa-openssl-rand-hex-32")
ALGORITHM   = "HS256"
EXPIRE_DAYS = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", 7))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Passwords ─────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    # bcrypt tiene un límite de 72 bytes — truncamos para evitar error en Vercel
    return pwd_context.hash(plain.encode("utf-8")[:72])

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain.encode("utf-8")[:72], hashed)


# ── Tokens ────────────────────────────────────────────────────────────────────

def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=EXPIRE_DAYS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# ── Dependencia: usuario actual ───────────────────────────────────────────────

def get_current_user(
    auth_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db)
) -> User:
    if not auth_token:
        raise HTTPException(status_code=401, detail="No autenticado")

    user_id = decode_token(auth_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    return user
