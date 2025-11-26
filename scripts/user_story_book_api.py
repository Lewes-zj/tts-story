"""用户有声故事书API"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from scripts.user_story_book_dao import UserStoryBookDAO
from scripts.auth_api import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user_story_books", tags=["用户有声故事书管理"])

# 创建DAO实例
user_story_book_dao = UserStoryBookDAO()


class UserStoryBookItem(BaseModel):
    """用户有声故事书项"""
    id: int
    storyId: int
    roleId: int
    storyBookPath: str
    createTime: str


class UserStoryBookListResponse(BaseModel):
    """用户有声故事书列表响应"""
    list: List[UserStoryBookItem]
    total: int
    page: int
    size: int


@router.get("", response_model=UserStoryBookListResponse)
async def get_user_story_books(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """获取用户的有声故事书列表"""
    try:
        user_id = current_user["user_id"]
        books = user_story_book_dao.find_list_by_user_id(user_id, page=page, size=size)
        total = user_story_book_dao.count_by_user_id(user_id)
        
        book_items = [
            UserStoryBookItem(
                id=book["id"],
                storyId=book["story_id"],
                roleId=book["role_id"],
                storyBookPath=book["story_book_path"],
                createTime=book["create_time"].isoformat() if book.get("create_time") else ""
            )
            for book in books
        ]
        
        return UserStoryBookListResponse(
            list=book_items,
            total=total,
            page=page,
            size=size
        )
    except Exception as e:
        logger.error(f"获取有声故事书列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取有声故事书列表失败: {str(e)}")

