"""
FastAPI 主应用

提供音频生成任务的API接口:
- POST /api/generate - 创建新任务
- GET /api/task/{task_id} - 查询任务状态
- GET /api/tasks - 列出所有任务
"""

import os
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)

# ============================================================================
# FastAPI 应用初始化
# ============================================================================

app = FastAPI(
    title="TTS Story Audio Generation API",
    description="音频生成流水线 API - 支持语音克隆、去静音、序列构建和对齐合成",
    version="1.0.0",
)

# 对外基础地址（用于生成可访问的音频URL），可通过环境变量覆盖
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

# CORS 配置 (允许跨域请求)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议配置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 线程池执行器 (用于后台任务)
executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="audio_pipeline_")

# 静态资源挂载：暴露生成任务输出目录，供前端播放音频
app.mount(
    "/media",
    StaticFiles(directory="data/tasks", check_dir=False),
    name="media",
)

# ============================================================================
# API 端点
# ============================================================================


@app.get("/")
async def root():
    """根路径 - API信息"""
    return {
        "name": "TTS Story Audio Generation API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "POST /api/generate": "创建音频生成任务 (基于路径)",
            "POST /api/generate_by_ids": "创建音频生成任务 (基于ID)",
            "GET /api/task/{task_id}": "查询任务状态",
            "GET /api/tasks": "列出所有任务",
        },
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "message": "Service is running"}


@app.post("/api/generate", response_model=TaskResponse)
async def create_generate_task(request: GenerateAudioRequest):
    """
    创建音频生成任务

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


@app.post("/api/generate_by_ids", response_model=TaskResponse)
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


@app.get("/api/task/{task_id}", response_model=TaskStatusResponse)
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


@app.get("/api/tasks", response_model=TaskListResponse)
async def list_all_tasks(
    limit: int = 100,
    status: str = None,
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


@app.delete("/api/task/{task_id}")
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
# 应用生命周期事件
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("=" * 70)
    logger.info("🚀 TTS Story Audio Generation API 启动中...")
    logger.info("=" * 70)
    logger.info(f"📂 任务管理器已初始化")
    logger.info(f"🔧 线程池已就绪 (max_workers=5)")
    logger.info(f"🎯 GPU 并发限制: 1 (同时最多1个任务执行AI推理)")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("👋 服务正在关闭...")
    executor.shutdown(wait=True)
    logger.info("✅ 线程池已停止")


# ============================================================================
# 异常处理
# ============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"❌ 未处理的异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误",
            "error": str(exc),
        },
    )


# ============================================================================
# 启动入口
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式，生产环境设为 False
        log_level="info",
    )
