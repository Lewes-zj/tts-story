"""JWT工具类"""

import jwt
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# JWT配置
JWT_SECRET = "tts-story-secret-key-2024"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


def generate_token(user_id: int, username: str) -> str:
    """生成JWT token"""
    payload = {
        "userId": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # PyJWT 2.x返回字符串，确保返回字符串类型
    return str(token) if isinstance(token, bytes) else token


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """验证JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token已过期")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Token无效")
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """从token中获取用户ID"""
    payload = verify_token(token)
    if payload:
        return payload.get("userId")
    return None


def get_username_from_token(token: str) -> Optional[str]:
    """从token中获取用户名"""
    payload = verify_token(token)
    if payload:
        return payload.get("username")
    return None

