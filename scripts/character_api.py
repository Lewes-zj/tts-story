"""角色管理API"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List
from scripts.character_dao import CharacterDAO
from scripts.auth_api import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/characters", tags=["角色管理"])

# 创建DAO实例
character_dao = CharacterDAO()


class CharacterRequest(BaseModel):
    """创建角色请求"""
    name: str = Field(..., min_length=2, max_length=6, description="角色名称，2-6个字符")


class CharacterResponse(BaseModel):
    """角色响应"""
    id: str
    name: str
    createdAt: str


@router.post("", response_model=CharacterResponse)
async def create_character(request: CharacterRequest, current_user: dict = Depends(get_current_user)):
    """创建角色"""
    try:
        user_id = current_user["user_id"]
        role_id = character_dao.insert(role_name=request.name, user_id=user_id)
        
        role = character_dao.find_by_id(role_id)
        if not role:
            raise HTTPException(status_code=500, detail="角色创建失败")
        
        return CharacterResponse(
            id=str(role["id"]),
            name=role["role_name"],
            createdAt=role["create_time"].isoformat() if role.get("create_time") else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建角色失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建角色失败: {str(e)}")


@router.get("", response_model=List[CharacterResponse])
async def get_user_characters(current_user: dict = Depends(get_current_user)):
    """获取用户角色列表"""
    try:
        user_id = current_user["user_id"]
        characters = character_dao.find_by_user_id(user_id)
        
        return [
            CharacterResponse(
                id=str(char["id"]),
                name=char["role_name"],
                createdAt=char["create_time"].isoformat() if char.get("create_time") else ""
            )
            for char in characters
        ]
    except Exception as e:
        logger.error(f"获取角色列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取角色列表失败: {str(e)}")

