"""
情绪向量处理API
使用FastAPI封装情绪向量处理功能
"""

import sys
import os

# 添加项目根目录到Python路径，确保能正确导入indextts
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os

# 导入情绪向量处理器
from scripts.emo_vector_processor import EmoVectorProcessor

# 导入用户情绪音频DAO
from scripts.user_emo_audio_dao import UserEmoAudioDAO

# 导入情绪向量配置DAO
from scripts.emo_vector_config_dao import EmoVectorConfigDAO

# 创建FastAPI应用实例
app = FastAPI(title="情绪向量处理API", description="根据情绪向量生成语音的API")

# 创建处理器和DAO实例
emo_processor = EmoVectorProcessor()
user_emo_dao = UserEmoAudioDAO()
emo_config_dao = EmoVectorConfigDAO()


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
    try:
        # 使用处理器生成情绪向量语音
        result_list = emo_processor.process_emo_vectors(
            input_audio=request.clean_input_audio, text=request.text
        )

        # 将结果存入user_emo_audio表
        saved_records = []
        for result in result_list:
            # 保存到数据库
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

        return EmoVectorResponse(
            user_id=request.user_id,
            role_id=request.role_id,
            text=request.text,
            generated_files=saved_records,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理情绪向量时发生错误: {str(e)}")


@app.get("/", summary="API根路径")
async def root():
    """
    API根路径

    Returns:
        dict: 欢迎信息
    """
    return {"message": "欢迎使用情绪向量处理API", "version": "1.0.0"}


# 如果直接运行此文件，则启动服务器
