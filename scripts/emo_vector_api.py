"""
情绪向量处理API
使用FastAPI封装情绪向量处理功能
"""

import sys
import os
import logging

from fastapi import FastAPI, HTTPException
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

# # 导入情绪向量配置DAO
# from scripts.emo_vector_config_dao import EmoVectorConfigDAO

# 创建FastAPI应用实例
app = FastAPI(title="情绪向量处理API", description="根据情绪向量生成语音的API")

# 创建处理器和DAO实例
logger.info("初始化EmoVectorProcessor...")
emo_processor = EmoVectorProcessor()
logger.info("初始化UserEmoAudioDAO...")
user_emo_dao = UserEmoAudioDAO()
# logger.info("初始化EmoVectorConfigDAO...")
# emo_config_dao = EmoVectorConfigDAO()
logger.info("所有组件初始化完成")


class EmoVectorRequest(BaseModel):
    """情绪向量处理请求模型"""

    user_id: int
    role_id: int
    clean_input_audio: str
    text: str


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


@app.post(
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
    logger.info(f"输入音频路径: {request.clean_input_audio}")
    logger.info(f"文本内容: {request.text}")
    
    try:
        # 使用处理器生成情绪向量语音
        logger.info("开始调用emo_processor.process_emo_vectors处理情绪向量...")
        result_list = emo_processor.process_emo_vectors(
            input_audio=request.clean_input_audio, text=request.text
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
                spk_emo_vector=result["spk_emo_vector"],
                spk_emo_alpha=result["spk_emo_alpha"],
                emo_audio_prompt=result["emo_audio_prompt"],
                emo_vector=result["emo_vector"],
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
            text=request.text,
            generated_files=saved_records,
        )
        logger.info("返回响应数据")
        return response

    except ValueError as e:
        logger.error(f"参数值错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"处理情绪向量时发生未预期的错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理情绪向量时发生错误: {str(e)}")


@app.get("/", summary="API根路径")
async def root():
    """
    API根路径

    Returns:
        dict: 欢迎信息
    """
    logger.info("访问API根路径")
    return {"message": "欢迎使用情绪向量处理API", "version": "1.0.0"}


# 如果直接运行此文件，则启动服务器
if __name__ == "__main__":
    import uvicorn
    logger.info("直接运行emo_vector_api.py，启动服务器...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
    