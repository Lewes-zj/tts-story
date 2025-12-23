"""故事管理API"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from scripts.story_dao import StoryDAO
import logging
import json
import os

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


class StoryPathResponse(BaseModel):
    """故事路径响应"""

    story_path: Optional[str] = None


# ==================== 新接口：从 JSON 文件读取故事数据 ====================
# 注意：这些路由必须在参数化路由之前定义，避免路径冲突


def _get_story_library_path() -> str:
    """获取故事库JSON文件路径"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "db", "story_library.json")


def _load_story_library() -> List[dict]:
    """从JSON文件加载故事库数据"""
    story_library_path = _get_story_library_path()

    if not os.path.exists(story_library_path):
        logger.error(f"故事库JSON文件不存在: {story_library_path}")
        return []

    try:
        with open(story_library_path, "r", encoding="utf-8") as f:
            stories = json.load(f)
            return stories if isinstance(stories, list) else []
    except Exception as e:
        logger.error(f"加载故事库JSON文件失败: {str(e)}")
        return []


@router.get("/json", response_model=StoryListResponse)
async def get_story_list_from_json(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, description="每页数量"),
):
    """从JSON文件获取故事列表"""
    try:
        stories = _load_story_library()
        total = len(stories)

        # 分页处理
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paginated_stories = stories[start_idx:end_idx]

        story_items = [
            StoryItem(
                id=story["id"],
                title=story["story_name"],
                category=story.get("category"),
                duration=str(story.get("duration", "")),
                coverUrl=story.get("cover_url"),
            )
            for story in paginated_stories
        ]

        return StoryListResponse(stories=story_items, total=total, page=page, size=size)
    except Exception as e:
        logger.error(f"从JSON获取故事列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取故事列表失败: {str(e)}")


@router.get("/json/{story_id}", response_model=StoryDetailResponse)
async def get_story_detail_from_json(story_id: str):
    """从JSON文件获取故事详情"""
    try:
        stories = _load_story_library()

        # 查找指定ID的故事（支持字符串和数字类型的id）
        story = next((s for s in stories if str(s["id"]) == str(story_id)), None)

        if not story:
            raise HTTPException(status_code=404, detail="故事不存在")

        # 读取故事内容
        content = ""
        script_json_path = story.get("script_json")
        if script_json_path:
            # 如果是相对路径，转换为绝对路径
            if not os.path.isabs(script_json_path):
                project_root = os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))
                )
                script_json_path = os.path.join(project_root, script_json_path)

            # 读取剧本JSON文件
            if os.path.exists(script_json_path):
                try:
                    with open(script_json_path, "r", encoding="utf-8") as f:
                        script_data = json.load(f)
                        # 提取对话内容
                        if isinstance(script_data, list):
                            content = "\n".join(
                                [
                                    item.get("text", "")
                                    for item in script_data
                                    if "text" in item
                                ]
                            )
                except Exception as e:
                    logger.warning(f"读取剧本JSON文件失败: {str(e)}")

        return StoryDetailResponse(
            id=story["id"],
            title=story["story_name"],
            category=story.get("category"),
            duration=str(story.get("duration", "")),
            coverUrl=story.get("cover_url"),
            content=content,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从JSON获取故事详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取故事详情失败: {str(e)}")


# ==================== 原有接口：从数据库读取故事数据 ====================


@router.get("", response_model=StoryListResponse)
async def get_story_list(
    category: Optional[str] = Query(None, description="分类筛选"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, description="每页数量"),
):
    """获取故事列表（从数据库）"""
    try:
        stories = story_dao.find_list(category=category, page=page, size=size)
        total = story_dao.count(category=category)

        story_items = [
            StoryItem(
                id=str(story["id"]),
                title=story["story_name"],
                category=story.get("category"),
                duration=story.get("duration"),
                coverUrl=story.get("cover_url"),
            )
            for story in stories
        ]

        return StoryListResponse(stories=story_items, total=total, page=page, size=size)
    except Exception as e:
        logger.error(f"获取故事列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取故事列表失败: {str(e)}")


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


@router.get("/{story_id}", response_model=StoryDetailResponse)
async def get_story_detail(story_id: int):
    """获取故事详情（从数据库）"""
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
            content=content,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取故事详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取故事详情失败: {str(e)}")
