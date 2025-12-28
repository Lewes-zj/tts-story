"""角色管理API"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import logging
import shutil
import time
import stat
from typing import Optional
import requests
from urllib.parse import urlparse  # 新增：用于解析URL
from scripts.character_dao import CharacterDAO
from scripts.user_input_audio_dao import UserInputAudioDAO
from scripts.file_dao import FileDAO
from scripts.auth_api import get_current_user
from scripts.audio_processor import process_audio_with_deepfilternet_denoiser
from scripts.auto_voice_cloner import AutoVoiceCloner
from scripts.cosyvoice_v3 import CosyVoiceV3

logger = logging.getLogger(__name__)

# 输出目录配置（与audio_tts.py保持一致）
# 获取项目根目录，构建outputs目录的绝对路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS_DIR = os.path.join(project_root, "outputs")
# Golden Master Prompt 音频路径
GOLDEN_MASTER_PROMPT = os.path.join(project_root, "prompt", "golden_master_prompt.MP3")
router = APIRouter(prefix="/api/characters", tags=["角色管理"])

# 确保输出目录存在
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# 创建DAO实例
character_dao = CharacterDAO()
user_input_audio_dao = UserInputAudioDAO()
file_dao = FileDAO()


def ensure_file_accessible(file_path: str, max_retries: int = 5, retry_delay: float = 0.5) -> bool:
    """
    确保文件可以被HTTP访问（文件系统层面）
    """
    for attempt in range(max_retries):
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.warning(f"文件不存在 (尝试 {attempt + 1}/{max_retries}): {file_path}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return False
            
            # 确保文件权限为可读（添加读取权限）
            current_permissions = os.stat(file_path).st_mode
            # 添加用户、组、其他用户的读取权限
            os.chmod(file_path, current_permissions | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            
            # 关键：确保所有父目录都有执行权限（x权限），否则无法访问文件
            dir_path = os.path.dirname(file_path)
            while dir_path and dir_path != os.path.dirname(dir_path):  # 直到根目录
                try:
                    if os.path.exists(dir_path):
                        dir_permissions = os.stat(dir_path).st_mode
                        # 添加执行权限（x权限），允许进入目录
                        os.chmod(dir_path, dir_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    dir_path = os.path.dirname(dir_path)
                except (OSError, PermissionError):
                    break
            
            # 刷新文件系统缓存
            try:
                with open(file_path, 'rb') as f:
                    f.read(1)
                    try:
                        os.fsync(f.fileno())
                    except (AttributeError, OSError):
                        pass
            except Exception:
                pass
            
            return True
                
        except Exception as e:
            logger.warning(f"验证文件可访问性时出错: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return False
    
    return False


def ensure_file_accessible_via_http(
    file_path: str, 
    http_url: str, 
    max_retries: int = 3,  # 减少重试次数，避免死锁时卡太久
    retry_delay: float = 1.0,
    timeout: float = 2.0,  # 减少超时时间
    use_localhost: bool = True
) -> bool:
    """
    确保文件可以通过HTTP URL访问
    优化：使用 User-Agent 伪装，并优先使用 localhost 绕过网关
    """
    # 构造请求头，伪装成浏览器，防止被网关 403 拦截
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 优先使用 localhost 进行验证
    # 注意：这里仅用于验证文件服务是否就绪，防止请求公网时被拦截或绕路
    target_url = http_url
    if use_localhost:
        try:
            parsed = urlparse(http_url)
            # 强制指向本地 8000 端口，路径保持不变
            # 这样验证请求就在服务器内部完成，不经过外部网关
            target_url = f"http://127.0.0.1:8000{parsed.path}"
            logger.debug(f"验证 URL (内部通道): {target_url}")
        except Exception:
            target_url = http_url
    
    for attempt in range(max_retries):
        try:
            # 发送 HEAD 请求检查文件
            response = requests.head(
                target_url, 
                headers=headers, 
                timeout=timeout, 
                allow_redirects=True
            )
            
            if response.status_code == 200:
                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > 0:
                    logger.info(f"文件 HTTP 验证通过: {target_url}")
                    return True
            elif response.status_code == 404:
                logger.warning(f"HTTP 404 (尝试 {attempt + 1}/{max_retries}): 文件暂未就绪")
            else:
                logger.warning(f"HTTP {response.status_code} (尝试 {attempt + 1}/{max_retries})")

            # 如果失败且还有重试机会，等待后重试
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                
        except requests.exceptions.ConnectionError:
            # 如果连不上 localhost，说明服务可能堵死了
            logger.warning(f"无法连接到验证地址 (尝试 {attempt + 1}/{max_retries}) - 服务可能繁忙")
            if attempt < max_retries - 1: time.sleep(retry_delay)
        except Exception as e:
            logger.warning(f"验证 HTTP 访问异常: {str(e)}")
            if attempt < max_retries - 1: time.sleep(retry_delay)
    
    logger.error(f"文件 HTTP 验证最终失败，但将尝试继续执行流程。")
    return False


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
    cosy_voice: Optional[str] = None
    tts_voice: Optional[str] = None


@router.post("", response_model=CharacterResponse)
async def create_character(
    request: CharacterRequest, current_user: dict = Depends(get_current_user)
):
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
                    # 创建用户专属目录: outputs/{user_id}/{role_id}/
                    user_role_dir = os.path.join(OUTPUTS_DIR, str(user_id), str(role_id))
                    os.makedirs(user_role_dir, exist_ok=True)
                    
                    # 设置目录权限：rwxr-xr-x (755)
                    os.chmod(user_role_dir, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                    
                    # 确保父目录也有执行权限
                    parent_dir = os.path.dirname(user_role_dir)
                    if os.path.exists(parent_dir):
                        os.chmod(parent_dir, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                    
                    logger.info(f"创建用户角色目录: {user_role_dir}")

                    # 获取文件名
                    file_name = file_record.get("file_name", "")

                    if not file_name or not file_name.endswith(".wav"):
                        file_url = file_record.get("file_url", "")
                        if file_url:
                            file_name = os.path.basename(file_url)
                        else:
                            file_name = f"{file_id}.wav"

                    if not file_name.endswith(".wav"):
                        file_name = f"{os.path.splitext(file_name)[0]}.wav"

                    # 构建完整的文件路径
                    init_input = os.path.join(user_role_dir, file_name)
                    init_input = os.path.abspath(init_input)

                    # 移动或复制文件
                    original_file_path = os.path.join(OUTPUTS_DIR, file_name)
                    if os.path.exists(original_file_path) and original_file_path != init_input:
                        if os.path.exists(init_input):
                            os.remove(init_input)
                        shutil.move(original_file_path, init_input)
                        logger.info(f"已移动文件到用户目录: {init_input}")

                    if not os.path.exists(init_input):
                        logger.warning(f"音频文件不存在: {init_input}，但仍保存记录到数据库")
                        user_input_audio_dao.insert(
                            user_id=user_id,
                            role_id=role_id,
                            init_input=init_input,
                            clean_input=None,
                            cosy_voice=None,
                            tts_voice=None,
                        )
                    else:
                        # 步骤1: 使用 DeepFilterNet -> Denoiser 处理音频
                        logger.info(f"步骤1: 开始降噪处理音频: {init_input}")
                        clean_input_path = None
                        try:
                            base_name = os.path.splitext(file_name)[0]
                            clean_output_path = os.path.join(user_role_dir, f"{base_name}_clean.wav")
                            clean_output_path = os.path.abspath(clean_output_path)

                            clean_input_path = process_audio_with_deepfilternet_denoiser(
                                input_path=init_input,
                                output_path=clean_output_path,
                                device=None,
                            )
                            if clean_input_path:
                                clean_input_path = os.path.abspath(clean_input_path)
                                logger.info(f"音频降噪成功: {clean_input_path}")
                                
                                # 确保文件系统已同步
                                if not ensure_file_accessible(clean_input_path):
                                    logger.warning("降噪音频文件验证失败，但继续处理")
                            else:
                                logger.warning("音频降噪失败，跳过后续克隆步骤")
                        except Exception as e:
                            logger.error(f"音频降噪异常: {str(e)}")
                            clean_input_path = None

                        fixed_text = "小朋友们大家好，这是一段黄金母本的音频，这段音频的主要目的呀，是为后续的所有音频克隆提供一段完美的音频输入"

                        # 步骤2: 使用 CosyVoice V3 进行声音克隆
                        cosy_voice_path = None
                        if clean_input_path and os.path.exists(clean_input_path):
                            logger.info(f"步骤2: 开始 CosyVoice V3 克隆，input_audio={clean_input_path}")
                            try:
                                public_base_url = os.getenv("PUBLIC_BASE_URL")
                                if not public_base_url:
                                    logger.warning("PUBLIC_BASE_URL 未配置，跳过 CosyVoice V3 处理")
                                else:
                                    time.sleep(0.5) # 等待文件系统
                                    
                                    clean_file_name = os.path.basename(clean_input_path)
                                    audio_url = f"{public_base_url.rstrip('/')}/outputs/{user_id}/{role_id}/{clean_file_name}"
                                    logger.info(f"CosyVoice 音频URL: {audio_url}")
                                    
                                    # 尝试验证 HTTP 可访问性 (改进版)
                                    # 如果验证失败，不应该中断流程，而是记录错误并继续尝试
                                    verification_success = ensure_file_accessible_via_http(
                                        clean_input_path, 
                                        audio_url, 
                                        max_retries=3, 
                                        retry_delay=1.0
                                    )
                                    
                                    if not verification_success:
                                        logger.warning("HTTP 验证未通过，但这可能是由于单线程死锁导致的。将尝试强行进行 CosyVoice 处理。")
                                    
                                    cosy_output_path = os.path.join(user_role_dir, f"{base_name}_cosyvoice.mp3")
                                    cosy_output_path = os.path.abspath(cosy_output_path)

                                    cosy_voice_client = CosyVoiceV3()
                                    cosy_voice_client.synthesize(
                                        audio_url=audio_url,
                                        text_to_synthesize=fixed_text,
                                        output_file=cosy_output_path,
                                    )

                                    if os.path.exists(cosy_output_path):
                                        cosy_voice_path = cosy_output_path
                                        logger.info(f"CosyVoice V3 克隆成功: {cosy_voice_path}")
                                    else:
                                        logger.warning("CosyVoice V3 克隆失败，输出文件不存在")
                            except Exception as e:
                                logger.error(f"CosyVoice V3 克隆异常: {str(e)}")
                                cosy_voice_path = None
                        else:
                            logger.warning("降噪音频不可用，跳过 CosyVoice V3 处理")

                        # 步骤3: 使用 AutoVoiceCloner 进行最终声音克隆
                        tts_voice_path = None
                        input_for_cloning = cosy_voice_path if cosy_voice_path and os.path.exists(cosy_voice_path) else clean_input_path

                        if input_for_cloning and os.path.exists(input_for_cloning):
                            logger.info(f"步骤3: 开始 AutoVoiceCloner 克隆，input_audio={input_for_cloning}")
                            try:
                                if not os.path.exists(GOLDEN_MASTER_PROMPT):
                                    logger.error(f"Golden Master Prompt 文件不存在: {GOLDEN_MASTER_PROMPT}")
                                    tts_voice_path = None
                                else:
                                    voice_cloner = AutoVoiceCloner(output_dir=user_role_dir)
                                    clone_result = voice_cloner.run_cloning(
                                        input_audio=input_for_cloning,
                                        emo_audio=GOLDEN_MASTER_PROMPT,
                                        emo_text=fixed_text,
                                    )

                                    if clone_result.get("success") > 0 and clone_result.get("results"):
                                        cloned_path = clone_result["results"][0].get("output_path")
                                        if cloned_path and os.path.exists(cloned_path):
                                            tts_voice_path = os.path.abspath(cloned_path)
                                            logger.info(f"AutoVoiceCloner 克隆成功: {tts_voice_path}")
                                        else:
                                            logger.warning("AutoVoiceCloner 克隆失败，输出文件不存在")
                                    else:
                                        error_msg = clone_result.get("results", [{}])[0].get("error", "未知错误")
                                        logger.warning(f"AutoVoiceCloner 克隆失败: {error_msg}")
                            except Exception as e:
                                logger.error(f"AutoVoiceCloner 克隆异常: {str(e)}")
                                tts_voice_path = None
                        else:
                            logger.warning("输入音频不可用，跳过 AutoVoiceCloner 处理")

                        # 插入记录
                        user_input_audio_dao.insert(
                            user_id=user_id,
                            role_id=role_id,
                            init_input=init_input,
                            clean_input=clean_input_path,
                            cosy_voice=cosy_voice_path,
                            tts_voice=tts_voice_path,
                        )
                        logger.info(f"已保存录音到user_input_audio表: role_id={role_id}")
            except (ValueError, Exception) as e:
                logger.warning(f"保存录音到user_input_audio表失败: {str(e)}")

        role = character_dao.find_by_id(role_id)
        if not role:
            raise HTTPException(status_code=500, detail="角色创建失败")

        return CharacterResponse(
            id=str(role["id"]),
            name=role["role_name"],
            createdAt=role["create_time"].isoformat() if role.get("create_time") else "",
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
                createdAt=char["create_time"].isoformat() if char.get("create_time") else "",
            )
            for char in characters
        ]
    except Exception as e:
        logger.error(f"获取角色列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取角色列表失败: {str(e)}")


@router.get("/{character_id}/audio", response_model=CharacterAudioResponse)
async def get_character_audio(
    character_id: int, current_user: dict = Depends(get_current_user)
):
    """获取角色的音频路径"""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="用户信息无效")

        character = character_dao.find_by_id(character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")

        if not character_dao.belongs_to_user(character_id, user_id):
            raise HTTPException(status_code=403, detail="无权访问该角色")

        audio_info = user_input_audio_dao.find_by_user_and_role(user_id, character_id)

        if not audio_info:
            return CharacterAudioResponse(
                clean_input_audio=None,
                init_input=None,
                cosy_voice=None,
                tts_voice=None,
            )

        return CharacterAudioResponse(
            clean_input_audio=audio_info.get("clean_input"),
            init_input=audio_info.get("init_input"),
            cosy_voice=audio_info.get("cosy_voice"),
            tts_voice=audio_info.get("tts_voice"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取角色音频路径失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取角色音频路径失败: {str(e)}")