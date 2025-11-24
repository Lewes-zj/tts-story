"""密码加密工具类"""

import bcrypt
import logging

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """
    加密密码
    
    Args:
        password: 明文密码
        
    Returns:
        str: 加密后的密码（bcrypt hash）
    """
    # 生成盐并加密密码
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        password: 明文密码
        hashed_password: 加密后的密码
        
    Returns:
        bool: 密码是否匹配
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        logger.error(f"密码验证失败: {str(e)}")
        return False

