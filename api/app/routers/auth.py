from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from jose import jwt
import bcrypt
from datetime import datetime, timedelta
from app.core.config import settings

router = APIRouter()

_oms_engine = create_async_engine(settings.OMS_DATABASE_URL, echo=False)
_OmsSession = sessionmaker(_oms_engine, class_=AsyncSession, expire_on_commit=False)

async def get_oms_db():
    async with _OmsSession() as session:
        yield session

def create_access_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({**data, "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

@router.post("/login")
async def login(body: dict, db: AsyncSession = Depends(get_oms_db)):
    result = await db.execute(
        text("SELECT app_user_id, email, password_hash FROM flow_ops.app_users WHERE email = :email AND is_active = true"),
        {"email": body.get("email")}
    )
    user = result.mappings().first()
    if not user or not verify_password(body.get("password", ""), user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user["app_user_id"]), "email": user["email"]})
    return {"access_token": token, "token_type": "bearer"}
