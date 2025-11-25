"""
情绪向量处理API
使用FastAPI封装情绪向量处理功能
"""

import sys
import os
import logging

from fastapi import HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入情绪向量处理器
from scripts.emo_vector_processor import EmoVectorProcessor

# 导入用户情绪音频DAO
from scripts.user_emo_audio_dao import UserEmoAudioDAO

# 导入用户输入音频DAO
from scripts.user_input_audio_dao import UserInputAudioDAO

# # 导入情绪向量配置DAO
# from scripts.emo_vector_config_dao import EmoVectorConfigDAO

# 创建APIRouter实例
from fastapi import APIRouter
router = APIRouter(prefix="/emo_vector", tags=["情绪向量处理"])

# 创建处理器和DAO实例
logger.info("初始化EmoVectorProcessor...")
emo_processor = EmoVectorProcessor()
logger.info("初始化UserEmoAudioDAO...")
user_emo_dao = UserEmoAudioDAO()
logger.info("初始化UserInputAudioDAO...")
user_input_audio_dao = UserInputAudioDAO()
# logger.info("初始化EmoVectorConfigDAO...")
# emo_config_dao = EmoVectorConfigDAO()
logger.info("所有组件初始化完成")

# 用于防止重复处理的请求ID集合（简单的内存去重）
processing_requests = set()


class EmoVectorRequest(BaseModel):
    """情绪向量处理请求模型"""

    user_id: int
    role_id: int
    # clean_input_audio 和 text 不再需要前端传递，后端会从数据库查询或使用默认值


class GeneratedFile(BaseModel):
    """生成文件信息模型"""

    record_id: int
    emo_type: str
    output_path: str
    text: str


class EmoVectorResponse(BaseModel):
    """情绪向量处理响应模型"""

    user_id: int
    role_id: int
    text: str
    generated_files: List[GeneratedFile]


@router.post(
    "/process_emo_vector/", response_model=EmoVectorResponse, summary="处理情绪向量"
)
async def process_emo_vector(request: EmoVectorRequest):
    """
    处理情绪向量，生成不同情绪的语音文件

    Args:
        request (EmoVectorRequest): 包含user_id, role_id, clean_input_audio, text的请求数据

    Returns:
        EmoVectorResponse: 处理结果，包含生成的音频文件信息
    """
    logger.info(f"收到处理情绪向量请求: user_id={request.user_id}, role_id={request.role_id}")
    
    # 创建请求唯一标识，防止重复处理
    request_id = f"{request.user_id}_{request.role_id}"
    
    # 检查是否正在处理相同的请求
    if request_id in processing_requests:
        logger.warning(f"检测到重复请求，忽略: user_id={request.user_id}, role_id={request.role_id}")
        raise HTTPException(
            status_code=409, 
            detail="该请求正在处理中，请勿重复提交"
        )
    
    # 标记请求为处理中
    processing_requests.add(request_id)
    
    try:
        # 从数据库查询 clean_input_audio
        logger.info(f"从数据库查询用户输入音频: user_id={request.user_id}, role_id={request.role_id}")
        audio_info = user_input_audio_dao.find_by_user_and_role(request.user_id, request.role_id)
        
        if not audio_info or not audio_info.get("clean_input"):
            logger.error(f"未找到用户输入音频: user_id={request.user_id}, role_id={request.role_id}")
            raise HTTPException(
                status_code=404, 
                detail="角色音频文件不存在，请先为角色上传音频并等待处理完成"
            )
        
        clean_input_audio = audio_info.get("clean_input")
        logger.info(f"从数据库获取到输入音频路径: {clean_input_audio}")
        
        # 使用固定的文本内容
        text = "床前明月光，疑是地上霜。举头望明月，低头思故乡。这首古诗陪伴我们成长，承载着无数人的美好回忆。"
        logger.info(f"使用固定文本内容: {text}")
        
        # 使用处理器生成情绪向量语音
        logger.info("开始调用emo_processor.process_emo_vectors处理情绪向量...")
        result_list = emo_processor.process_emo_vectors(
            input_audio=clean_input_audio, text=text
        )
        logger.info(f"emo_processor处理完成，共生成{len(result_list)}个结果")

        # 将结果存入user_emo_audio表
        logger.info("开始将结果存入数据库...")
        saved_records = []
        for i, result in enumerate(result_list):
            logger.info(f"处理第{i+1}/{len(result_list)}个结果，情绪类型: {result['emo_type']}")
            
            # 保存到数据库
            logger.info(f"插入数据库记录: user_id={request.user_id}, role_id={request.role_id}, emo_type={result['emo_type']}")
            record_id = user_emo_dao.insert(
                user_id=request.user_id,
                role_id=request.role_id,
                emo_type=result["emo_type"],
                spk_audio_prompt=result["spk_audio_prompt"],
                spk_emo_vector=str(result["spk_emo_vector"]).replace(' ', '').replace('0.0', '0'),  # 转换为字符串并格式化为数据库兼容格式
                spk_emo_alpha=result["spk_emo_alpha"],
                emo_audio_prompt=result["emo_audio_prompt"],
                emo_vector=str(result["emo_vector"]).replace(' ', '').replace('0.0', '0'),  # 转换为字符串并格式化为数据库兼容格式
                emo_alpha=result["emo_alpha"],
            )
            logger.info(f"数据库记录插入成功，记录ID: {record_id}")

            # 添加到返回结果中
            # 使用spk_audio_prompt作为主要输出路径
            saved_records.append(
                GeneratedFile(
                    record_id=record_id,
                    emo_type=result["emo_type"],
                    output_path=result["spk_audio_prompt"],
                    text=result["text"],
                )
            )
            logger.info(f"第{i+1}/{len(result_list)}个结果处理完成")

        logger.info(f"所有结果处理完成，共处理{len(saved_records)}个记录")
        response = EmoVectorResponse(
            user_id=request.user_id,
            role_id=request.role_id,
            text=text,
            generated_files=saved_records,
        )
        logger.info("返回响应数据")
        return response

    except HTTPException:
        # HTTPException 需要重新抛出，finally块会清理请求标记
        raise
    except ValueError as e:
        logger.error(f"参数值错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"处理情绪向量时发生未预期的错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理情绪向量时发生错误: {str(e)}")
    finally:
        # 确保无论成功还是失败，都清理请求标记
        processing_requests.discard(request_id)
        logger.debug(f"清理请求标记: {request_id}")


@router.get("/", summary="API根路径")
async def root():
    """
    API根路径

    Returns:
        dict: 欢迎信息
    """
    logger.info("访问API根路径")
    return {"message": "欢迎使用情绪向量处理API", "version": "1.0.0"}


# 如果直接运行此文件，则启动服务器（用于测试）
if __name__ == "__main__":
    from fastapi import FastAPI
    import uvicorn
    test_app = FastAPI(title="情绪向量处理API", description="根据情绪向量生成语音的API")
    test_app.include_router(router)
    logger.info("直接运行emo_vector_api.py，启动服务器...")
    uvicorn.run(test_app, host="0.0.0.0", port=8000)
    