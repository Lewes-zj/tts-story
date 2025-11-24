"""任务管理API"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from scripts.task_dao import TaskDAO
from scripts.auth_api import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])

# 创建DAO实例
task_dao = TaskDAO()


class TaskRequest(BaseModel):
    """创建任务请求"""
    storyId: int
    characterId: int


class TaskItem(BaseModel):
    """任务项"""
    id: str
    storyId: int
    characterId: int
    status: str
    createdAt: str
    audioUrl: Optional[str] = None  # 仅在completed状态时返回


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[TaskItem]
    total: int
    page: int
    size: int


class TaskDetailResponse(BaseModel):
    """任务详情响应"""
    id: str
    storyId: int
    characterId: int
    status: str
    createdAt: str
    audioUrl: Optional[str] = None  # 仅在completed状态时返回


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    status: str


@router.post("", response_model=TaskDetailResponse)
async def create_task(request: TaskRequest, current_user: dict = Depends(get_current_user)):
    """创建语音生成任务"""
    try:
        user_id = current_user["user_id"]
        task_id = task_dao.insert(
            user_id=user_id,
            story_id=request.storyId,
            character_id=request.characterId,
            status="generating"
        )
        
        task = task_dao.find_by_id(task_id)
        if not task:
            raise HTTPException(status_code=500, detail="任务创建失败")
        
        return TaskDetailResponse(
            id=str(task["id"]),
            storyId=task["story_id"],
            characterId=task["character_id"],
            status=task["status"],
            createdAt=task["create_time"].isoformat() if task.get("create_time") else "",
            audioUrl=task.get("audio_url") if task["status"] == "completed" else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.get("", response_model=TaskListResponse)
async def get_task_list(
    status: Optional[str] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """获取任务列表"""
    try:
        user_id = current_user["user_id"]
        tasks = task_dao.find_by_user_id(user_id, status=status, page=page, size=size)
        total = task_dao.count_by_user_id(user_id, status=status)
        
        task_items = [
            TaskItem(
                id=str(task["id"]),
                storyId=task["story_id"],
                characterId=task["character_id"],
                status=task["status"],
                createdAt=task["create_time"].isoformat() if task.get("create_time") else "",
                audioUrl=task.get("audio_url") if task["status"] == "completed" else None
            )
            for task in tasks
        ]
        
        return TaskListResponse(
            tasks=task_items,
            total=total,
            page=page,
            size=size
        )
    except Exception as e:
        logger.error(f"获取任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail(task_id: int, current_user: dict = Depends(get_current_user)):
    """获取任务详情"""
    try:
        user_id = current_user["user_id"]
        task = task_dao.find_by_id(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if task["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="无权访问该任务")
        
        return TaskDetailResponse(
            id=str(task["id"]),
            storyId=task["story_id"],
            characterId=task["character_id"],
            status=task["status"],
            createdAt=task["create_time"].isoformat() if task.get("create_time") else "",
            audioUrl=task.get("audio_url") if task["status"] == "completed" else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取任务详情失败: {str(e)}")


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: int):
    """获取任务状态"""
    try:
        task = task_dao.find_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return TaskStatusResponse(status=task["status"])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")

