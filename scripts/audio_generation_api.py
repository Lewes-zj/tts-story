"""
音频生成 API 路由
提供音频生成任务的API接口
"""

import uuid
import logging
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, HTTPException

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from app.models import (
    GenerateAudioRequest,
    GenerateByIdsRequest,
    TaskResponse,
    TaskStatusResponse,
    TaskListResponse,
    TaskStatus,
)
from app.services.task_manager import task_manager
from app.services.audio_pipeline import generate_audio_pipeline
from app.services.business_generate import business_generate_service

# ============================================================================
# 日志配置
# ============================================================================

logger = logging.getLogger(__name__)

# ============================================================================
# 线程池执行器
# ============================================================================

# 线程池执行器 (用于后台任务)
executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="audio_pipeline_")

# ============================================================================
# 创建路由器
# ============================================================================

router = APIRouter(prefix="", tags=["音频生成"])

# ============================================================================
# API 端点
# ============================================================================


@router.post("/api/generate", response_model=TaskResponse)
async def create_generate_task(request: GenerateAudioRequest):
    """
    创建音频生成任务（基于路径）

    接收请求参数，创建任务，在后台执行pipeline，立即返回task_id

    Args:
        request: 音频生成请求参数

    Returns:
        任务响应 (包含task_id)
    """
    try:
        # 生成唯一任务ID
        task_id = str(uuid.uuid4())

        # 创建任务记录
        task = task_manager.create_task(
            task_id=task_id,
            task_name=request.task_name,
            total_steps=4,
        )

        # 将请求参数转为字典
        params = request.model_dump()

        # 提交到线程池后台执行
        executor.submit(generate_audio_pipeline, task_id, params)

        logger.info(f"✅ 任务已提交: {task_id}")

        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            message="任务已创建，正在后台执行",
            created_at=task["created_at"],
        )

    except Exception as e:
        logger.error(f"❌ 创建任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.post("/api/generate_by_ids", response_model=TaskResponse)
async def create_generate_task_by_ids(request: GenerateByIdsRequest):
    """
    基于ID创建音频生成任务

    通过story_id、user_id、role_id自动查找配置和音频文件，
    无需前端提供绝对路径

    Args:
        request: 包含story_id、user_id、role_id的请求

    Returns:
        任务响应 (包含task_id)
    """
    try:
        logger.info(
            f"收到ID生成请求: story_id={request.story_id}, "
            f"user_id={request.user_id}, role_id={request.role_id}"
        )

        # 1. 准备生成参数 (配置文件读取 + 数据库查询)
        try:
            params = business_generate_service.prepare_generation_params(
                story_id=request.story_id,
                user_id=request.user_id,
                role_id=request.role_id,
                task_name=request.task_name,
            )
        except FileNotFoundError as e:
            logger.error(f"配置文件不存在: {str(e)}")
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            logger.error(f"参数错误: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

        # 2. 生成唯一任务ID
        task_id = str(uuid.uuid4())

        # 3. 创建任务记录
        task = task_manager.create_task(
            task_id=task_id,
            task_name=params.get("task_name", f"故事{request.story_id}生成"),
            total_steps=4,
        )

        # 4. 提交到线程池后台执行
        executor.submit(generate_audio_pipeline, task_id, params)

        logger.info(f"✅ ID生成任务已提交: {task_id}")

        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            message="任务已创建，正在后台执行",
            created_at=task["created_at"],
        )

    except HTTPException:
        # HTTPException需要重新抛出
        raise
    except Exception as e:
        logger.error(f"❌ 创建ID生成任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.get("/api/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    查询任务状态

    Args:
        task_id: 任务ID

    Returns:
        任务状态详情
    """
    task = task_manager.get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    # 将字典转为 Pydantic 模型
    try:
        return TaskStatusResponse(**task)
    except Exception as e:
        logger.error(f"❌ 返回任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"返回任务状态失败: {str(e)}")


@router.get("/api/tasks", response_model=TaskListResponse)
async def list_all_tasks(
    limit: int = 100,
    status: Optional[str] = None,
):
    """
    列出所有任务

    Args:
        limit: 返回数量限制
        status: 按状态筛选 (可选)

    Returns:
        任务列表
    """
    try:
        all_tasks = task_manager.get_all_tasks()

        # 按状态筛选
        if status:
            all_tasks = [t for t in all_tasks if t.get("status") == status]

        # 按创建时间倒序排序
        all_tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # 限制返回数量
        all_tasks = all_tasks[:limit]

        # 转为 Pydantic 模型
        task_list = [TaskStatusResponse(**task) for task in all_tasks]

        return TaskListResponse(
            total=len(task_list),
            tasks=task_list,
        )

    except Exception as e:
        logger.error(f"❌ 获取任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


@router.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    """
    删除任务

    Args:
        task_id: 任务ID

    Returns:
        删除结果
    """
    task = task_manager.get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    try:
        task_manager.delete_task(task_id)
        return {"message": f"任务已删除: {task_id}"}
    except Exception as e:
        logger.error(f"❌ 删除任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")


# ============================================================================
# 生命周期管理
# ============================================================================


def shutdown_audio_generation():
    """关闭音频生成服务的资源"""
    logger.info("👋 音频生成服务正在关闭...")
    executor.shutdown(wait=True)
    logger.info("✅ 线程池已停止")
