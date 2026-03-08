import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import User, get_db  # ✅ 从 database 导入 User

# 配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 方案
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class AuthService:
    """认证服务"""

class AuthService:
    """认证服务"""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码（统一使用 passlib）"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """密码哈希（统一使用 passlib）"""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(
        data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        """创建 JWT Token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def decode_access_token(token: str) -> Optional[dict]:
        """解码 JWT Token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None


# ==================== 依赖项 ====================


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """获取当前用户（用于需要登录的接口）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = AuthService.decode_access_token(token)
    if payload is None:
        raise credentials_exception

    # 🔹 从 token 中获取用户 ID（不再是 username）
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # 🔹 通过 ID 查询用户（✅ 更稳定，不受邮箱/用户名变更影响）
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user