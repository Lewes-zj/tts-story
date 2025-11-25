"""故事管理API"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from scripts.story_dao import StoryDAO
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stories", tags=["故事管理"])

# 创建DAO实例
story_dao = StoryDAO()


class StoryItem(BaseModel):
    """故事项"""
    id: str
    title: str
    category: Optional[str] = None
    duration: Optional[str] = None
    coverUrl: Optional[str] = None


class StoryListResponse(BaseModel):
    """故事列表响应"""
    stories: List[StoryItem]
    total: int
    page: int
    size: int


class StoryDetailResponse(BaseModel):
    """故事详情响应"""
    id: str
    title: str
    category: Optional[str] = None
    duration: Optional[str] = None
    coverUrl: Optional[str] = None
    content: str


<<<<<<< HEAD
=======
class StoryPathResponse(BaseModel):
    """故事路径响应"""
    story_path: Optional[str] = None


>>>>>>> 8fa09d4 (update)
@router.get("", response_model=StoryListResponse)
async def get_story_list(
    category: Optional[str] = Query(None, description="分类筛选"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, description="每页数量")
):
    """获取故事列表"""
    try:
        stories = story_dao.find_list(category=category, page=page, size=size)
        total = story_dao.count(category=category)
        
        story_items = [
            StoryItem(
                id=str(story["id"]),
                title=story["story_name"],
                category=story.get("category"),
                duration=story.get("duration"),
                coverUrl=story.get("cover_url")
            )
            for story in stories
        ]
        
        return StoryListResponse(
            stories=story_items,
            total=total,
            page=page,
            size=size
        )
    except Exception as e:
        logger.error(f"获取故事列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取故事列表失败: {str(e)}")


@router.get("/{story_id}", response_model=StoryDetailResponse)
async def get_story_detail(story_id: int):
    """获取故事详情"""
    try:
        story = story_dao.find_by_id(story_id)
        if not story:
            raise HTTPException(status_code=404, detail="故事不存在")
        
        # 获取故事内容
        content = story_dao.get_story_content(story_id)
        
        return StoryDetailResponse(
            id=str(story["id"]),
            title=story["story_name"],
            category=story.get("category"),
            duration=story.get("duration"),
            coverUrl=story.get("cover_url"),
            content=content
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取故事详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取故事详情失败: {str(e)}")


@router.get("/{story_id}/path", response_model=StoryPathResponse)
async def get_story_path(story_id: int):
    """获取故事的JSON文件路径"""
    try:
        # 验证故事是否存在
        story = story_dao.find_by_id(story_id)
        if not story:
            raise HTTPException(status_code=404, detail="故事不存在")
        
        # 获取故事路径
        story_path = story_dao.get_story_path(story_id)
        
        return StoryPathResponse(story_path=story_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取故事路径失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取故事路径失败: {str(e)}")

