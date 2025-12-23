"""
有声故事书生成API
提供生成有声故事书的RESTful API接口
"""

import os
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入有声故事书生成器
try:
    from scripts.story_book_generator import StoryBookGenerator
    STORY_BOOK_AVAILABLE = True
except ImportError:
    print("警告: 无法导入StoryBookGenerator，有声故事书功能将不可用")
    STORY_BOOK_AVAILABLE = False

# 导入用户有声故事书DAO
from scripts.user_story_book_dao import UserStoryBookDAO
# 导入任务DAO
from scripts.task_dao import TaskDAO

app = FastAPI(title="有声故事书生成API", description="根据用户选择的角色和故事生成有声故事书")

# 用于防止重复处理的请求ID集合（简单的内存去重）
processing_requests = set()
# 初始化DAO
user_story_book_dao = UserStoryBookDAO()
task_dao = TaskDAO()



class StoryBookRequest(BaseModel):
    """有声故事书生成请求模型"""
    user_id: int
    role_id: int
    story_id: int
    story_path: str
    keep_temp_files: Optional[bool] = None



class StoryBookResponse(BaseModel):
    """有声故事书生成响应模型"""
    success: bool
    message: str
    story_book_path: Optional[str] = None


@app.post("/story_book/generate", response_model=StoryBookResponse)
async def generate_story_book(request: StoryBookRequest):
    """
    生成有声故事书

    Args:
        request (StoryBookRequest): 生成请求参数

    Returns:
        StoryBookResponse: 生成结果
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not STORY_BOOK_AVAILABLE:
        raise HTTPException(status_code=500, detail="有声故事书功能不可用")

    # 创建请求唯一标识，防止重复处理
    # 使用 user_id, role_id, story_path 组合作为唯一标识
    request_id = f"{request.user_id}_{request.role_id}_{request.story_path}"
    
    # 检查是否正在处理相同的请求
    if request_id in processing_requests:
        logger.warning(f"检测到重复请求，忽略: user_id={request.user_id}, role_id={request.role_id}, story_path={request.story_path}")
        raise HTTPException(
            status_code=409, 
            detail="该请求正在处理中，请勿重复提交"
        )
    
    # 标记请求为处理中
    processing_requests.add(request_id)
    logger.info(f"开始处理有声故事书生成请求: user_id={request.user_id}, role_id={request.role_id}, story_id={request.story_id}, story_path={request.story_path}")

    try:
        # 1. 检查数据库中是否已经存在结果
        logger.info(f"检查数据库中是否存在已有结果: user_id={request.user_id}, role_id={request.role_id}, story_id={request.story_id}")
        existing_record = user_story_book_dao.find_by_user_role_story(request.user_id, request.role_id, request.story_id)
        
        if existing_record:
            stored_path = existing_record['story_book_path']
            story_book_path = user_story_book_dao.normalize_path(stored_path)
            logger.info(f"数据库中已存在记录，直接返回: {story_book_path}")
            # 如果已是可访问URL，直接返回；否则再检查本地文件是否存在
            if story_book_path.startswith(("http://", "https://")):
                return StoryBookResponse(
                    success=True,
                    message="有声故事书已存在",
                    story_book_path=story_book_path
                )
            if os.path.exists(story_book_path):
                return StoryBookResponse(
                    success=True,
                    message="有声故事书已存在",
                    story_book_path=story_book_path
                )
            else:
                logger.warning(f"数据库中有记录但文件不存在，重新生成: {story_book_path}")

        # 创建生成器实例
        generator = StoryBookGenerator()

        # 生成有声故事书
        story_book_path = generator.generate_story_book(
            user_id=request.user_id,
            role_id=request.role_id,
            story_path=request.story_path,
            keep_temp_files=request.keep_temp_files
        )

        if story_book_path:
            logger.info(f"有声故事书生成成功: {story_book_path}")

            # 构建可外网访问的完整路径
            public_path = user_story_book_dao.normalize_path(story_book_path)
            logger.info(f"保存到数据库的完整路径: {public_path}")

            # 保存到数据库
            try:
                # 1. 保存到用户有声故事书记录表
                user_story_book_dao.insert(
                    user_id=request.user_id,
                    role_id=request.role_id,
                    story_id=request.story_id,
                    story_book_path=public_path
                )
                logger.info("有声故事书记录保存到数据库成功")
                
                # 2. 保存到任务表（供畅听页面使用）
                # 检查是否已存在相同的已完成任务，避免重复
                existing_tasks = task_dao.find_by_user_id(request.user_id)
                # 简单的重复检查逻辑：查看最新的任务是否匹配
                # 注意：这里只是简单的插入，因为TaskDAO没有find_by_user_role_story这样的精确查询方法
                # 但为了确保畅听页面能看到，我们插入一条新记录
                task_id = task_dao.insert(
                    user_id=request.user_id,
                    story_id=request.story_id,
                    character_id=request.role_id,
                    status="completed"
                )
                # 更新音频URL
                task_dao.update(task_id=task_id, audio_url=public_path)
                logger.info(f"任务记录保存到数据库成功，task_id: {task_id}")

            except Exception as db_err:
                logger.error(f"保存有声故事书记录到数据库失败: {str(db_err)}")
                # 记录失败但不影响返回结果

            return StoryBookResponse(
                success=True,
                message="有声故事书生成成功",
                story_book_path=public_path
            )
        else:
            logger.error("有声故事书生成失败：返回路径为空")
            return StoryBookResponse(
                success=False,
                message="有声故事书生成失败"
            )

    except HTTPException:
        # HTTPException 需要重新抛出，finally块会清理请求标记
        raise
    except Exception as e:
        logger.error(f"生成有声故事书时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成有声故事书时出错: {str(e)}")
    finally:
        # 确保无论成功还是失败，都清理请求标记
        processing_requests.discard(request_id)
        logger.debug(f"清理请求标记: {request_id}")

# 为了方便测试，添加一个根路径


@app.get("/")
async def root():
    return {"message": "有声故事书生成API服务"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
