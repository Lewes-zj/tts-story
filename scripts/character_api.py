"""角色管理API"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import logging
from scripts.character_dao import CharacterDAO
from scripts.user_input_audio_dao import UserInputAudioDAO
from scripts.file_dao import FileDAO
from scripts.auth_api import get_current_user
from scripts.audio_processor import process_audio_with_deepfilternet_denoiser

logger = logging.getLogger(__name__)

# 导入UPLOAD_DIR配置
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/tts-story/uploads")
router = APIRouter(prefix="/api/characters", tags=["角色管理"])

# 创建DAO实例
character_dao = CharacterDAO()
user_input_audio_dao = UserInputAudioDAO()
file_dao = FileDAO()


class CharacterRequest(BaseModel):
    """创建角色请求"""
    name: str = Field(..., min_length=2, max_length=6, description="角色名称，2-6个字符")
    fileId: Optional[str] = Field(None, description="录音文件ID")


class CharacterResponse(BaseModel):
    """角色响应"""
    id: str
    name: str
    createdAt: str


class CharacterAudioResponse(BaseModel):
    """角色音频响应"""
    clean_input_audio: Optional[str] = None
    init_input: Optional[str] = None


@router.post("", response_model=CharacterResponse)
async def create_character(request: CharacterRequest, current_user: dict = Depends(get_current_user)):
    """创建角色"""
    try:
        user_id = current_user["user_id"]
        role_id = character_dao.insert(role_name=request.name, user_id=user_id)
        
        # 如果提供了fileId，保存到user_input_audio表
        if request.fileId:
            try:
                file_id = int(request.fileId)
                file_record = file_dao.find_by_id(file_id)
                if file_record:
                    # 获取文件名（应该已经是wav格式，因为上传时已转换）
                    file_name = file_record.get("file_name", "")

                    # 如果文件名为空或不是wav格式，尝试从file_url提取
                    if not file_name or not file_name.endswith('.wav'):
                        file_url = file_record.get("file_url", "")
                        if file_url:
                            # 从URL中提取文件名
                            file_name = os.path.basename(file_url)
                        else:
                            # 如果都没有，使用file_id生成文件名
                            file_name = f"{file_id}.wav"

                    # 确保文件名是wav格式
                    if not file_name.endswith('.wav'):
                        file_name = f"{os.path.splitext(file_name)[0]}.wav"

                    # 构建完整的文件路径（存储在upload目录下）
                    init_input = os.path.join(UPLOAD_DIR, file_name)

                    # 验证文件是否存在
                    if not os.path.exists(init_input):
                        logger.warning(f"音频文件不存在: {init_input}，但仍保存记录到数据库")
                        clean_input = None
                    else:
                        # 使用 DeepFilterNet -> Denoiser 处理音频
                        logger.info(f"开始处理音频: {init_input}")
                        try:
                            clean_input = process_audio_with_deepfilternet_denoiser(
                                input_path=init_input,
                                device=None  # 自动选择设备
                            )
                            if clean_input:
                                logger.info(f"音频处理成功: {clean_input}")
                            else:
                                logger.warning(f"音频处理失败，clean_input 将为 None")
                                clean_input = None
                        except Exception as e:
                            logger.error(f"音频处理异常: {str(e)}")
                            clean_input = None

                    # 先插入记录（clean_input 可能为 None，后续可以异步更新）
                    user_input_audio_dao.insert(
                        user_id=user_id,
                        role_id=role_id,
                        init_input=init_input,
                        clean_input=clean_input
                    )
                    logger.info(f"已保存录音到user_input_audio表: user_id={user_id}, role_id={role_id}, file_id={file_id}, file_path={init_input}, clean_input={clean_input}")
            except (ValueError, Exception) as e:
                logger.warning(f"保存录音到user_input_audio表失败: {str(e)}")
                # 即使保存失败，也不影响角色创建
        role = character_dao.find_by_id(role_id)
        if not role:
            raise HTTPException(status_code=500, detail="角色创建失败")
        
        return CharacterResponse(
            id=str(role["id"]),
            name=role["role_name"],
            createdAt=role["create_time"].isoformat() if role.get("create_time") else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建角色失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建角色失败: {str(e)}")


@router.get("", response_model=List[CharacterResponse])
async def get_user_characters(current_user: dict = Depends(get_current_user)):
    """获取用户角色列表"""
    try:
        user_id = current_user["user_id"]
        characters = character_dao.find_by_user_id(user_id)
        
        return [
            CharacterResponse(
                id=str(char["id"]),
                name=char["role_name"],
                createdAt=char["create_time"].isoformat() if char.get("create_time") else ""
            )
            for char in characters
        ]
    except Exception as e:
        logger.error(f"获取角色列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取角色列表失败: {str(e)}")


@router.get("/{character_id}/audio", response_model=CharacterAudioResponse)
async def get_character_audio(character_id: int, current_user: dict = Depends(get_current_user)):
    """获取角色的音频路径"""
    try:
        user_id = current_user["user_id"]

        # 验证角色是否属于当前用户
        character = character_dao.find_by_id(character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")

        if character["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="无权访问该角色")

        # 查询角色的音频信息
        audio_info = user_input_audio_dao.find_by_user_and_role(user_id, character_id)

        if not audio_info:
            return CharacterAudioResponse(
                clean_input_audio=None,
                init_input=None
            )

        return CharacterAudioResponse(
            clean_input_audio=audio_info.get("clean_input"),
            init_input=audio_info.get("init_input")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取角色音频路径失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取角色音频路径失败: {str(e)}")

