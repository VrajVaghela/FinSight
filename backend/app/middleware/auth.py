# app/middleware/auth.py
from fastapi import Request, HTTPException
from jose import jwt, JWTError
import os
import time

JWT_SECRET = os.getenv("JWT_SECRET", "hackathon_secret_key_change_me")
ALGORITHM = "HS256"

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = time.time() + 3600 * 24 # 24 hours
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)

async def verify_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
