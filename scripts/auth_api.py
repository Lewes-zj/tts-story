"""用户认证API"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from typing import Optional
from scripts.user_dao import UserDAO
from scripts.jwt_util import generate_token, verify_token
from scripts.password_util import hash_password, verify_password
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])

# 创建DAO实例
user_dao = UserDAO()


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    """注册响应"""
    id: str
    username: str
    email: str
    createdAt: str


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class UserInfo(BaseModel):
    """用户信息"""
    id: str
    username: str
    email: str


class LoginResponse(BaseModel):
    """登录响应"""
    user: UserInfo
    token: str


@router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest):
    """用户注册"""
    try:
        # 检查用户名是否已存在
        exist_user = user_dao.find_by_account(request.username)
        if exist_user:
            raise HTTPException(status_code=400, detail="用户名已存在")
        
        # 检查邮箱是否已存在
        exist_email = user_dao.find_by_email(request.email)
        if exist_email:
            raise HTTPException(status_code=400, detail="邮箱已被注册")
        
        # 加密密码
        hashed_password = hash_password(request.password)
        
        # 创建新用户
        user_id = user_dao.insert(
            account=request.username,
            email=request.email,
            password=hashed_password,  # 存储加密后的密码
            name=request.username
        )
        
        # 获取创建的用户信息
        user = user_dao.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=500, detail="用户创建失败")
        
        return RegisterResponse(
            id=str(user["id"]),
            username=user["account"],
            email=user.get("email", ""),
            createdAt=user["register_time"].isoformat() if user.get("register_time") else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """用户登录"""
    try:
        user = user_dao.find_by_account(request.username)
        if not user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        # 验证密码（使用bcrypt验证加密后的密码）
        if not verify_password(request.password, user["password"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        # 生成JWT token
        token = generate_token(user["id"], user["account"])
        
        return LoginResponse(
            user=UserInfo(
                id=str(user["id"]),
                username=user["account"],
                email=user.get("email", "")
            ),
            token=token
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


@router.post("/logout")
async def logout():
    """用户退出"""
    # JWT是无状态的，退出只需要客户端删除token即可
    return {"code": 200, "message": "success", "data": None}


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """获取当前用户（依赖注入）"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权")
    
    token = authorization[7:]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token无效或已过期")
    
    user_id = payload.get("userId")
    username = payload.get("username")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Token无效")
    
    return {"user_id": user_id, "username": username}

