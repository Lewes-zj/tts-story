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
    
    通过以下方式确保文件可访问：
    1. 确保文件存在
    2. 设置文件权限为可读
    3. 刷新文件系统缓存
    4. 验证文件可读
    
    Args:
        file_path: 文件路径
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
    
    Returns:
        bool: 文件是否可访问
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
            # 这是导致403错误的主要原因
            dir_path = os.path.dirname(file_path)
            while dir_path and dir_path != os.path.dirname(dir_path):  # 直到根目录
                try:
                    if os.path.exists(dir_path):
                        dir_permissions = os.stat(dir_path).st_mode
                        # 添加执行权限（x权限），允许进入目录
                        os.chmod(dir_path, dir_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                        logger.debug(f"已设置目录执行权限: {dir_path}")
                    dir_path = os.path.dirname(dir_path)
                except (OSError, PermissionError) as e:
                    logger.warning(f"设置目录权限时出错: {dir_path}, {str(e)}")
                    break
            
            # 刷新文件系统缓存（通过打开并关闭文件）
            try:
                with open(file_path, 'rb') as f:
                    f.read(1)  # 读取一个字节以触发文件系统同步
                    # 同步文件到磁盘
                    try:
                        os.fsync(f.fileno())  # Linux/Unix标准方法
                    except (AttributeError, OSError):
                        # Windows或不支持fsync的系统，尝试其他方法
                        try:
                            f.flush()
                        except:
                            pass
            except Exception as e:
                logger.warning(f"刷新文件缓存时出错: {str(e)}")
            
            # 验证文件可读
            try:
                with open(file_path, 'rb') as f:
                    f.read(1)
                logger.info(f"文件已验证可访问（文件系统）: {file_path}")
                return True
            except PermissionError:
                logger.warning(f"文件权限不足 (尝试 {attempt + 1}/{max_retries}): {file_path}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return False
                
        except Exception as e:
            logger.warning(f"验证文件可访问性时出错 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return False
    
    return False


def ensure_file_accessible_via_http(
    file_path: str, 
    http_url: str, 
    max_retries: int = 10, 
    retry_delay: float = 1.0,
    timeout: float = 5.0,
    use_localhost: bool = True
) -> bool:
    """
    确保文件可以通过HTTP URL访问
    
    通过实际HTTP请求验证文件是否可以通过URL访问。
    这可以确保FastAPI的StaticFiles已经识别到新文件。
    
    Args:
        file_path: 文件路径（用于日志）
        http_url: HTTP URL
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        timeout: HTTP请求超时时间（秒）
        use_localhost: 是否优先使用localhost验证（避免反向代理限制）
    
    Returns:
        bool: 文件是否可以通过HTTP访问
    """
    # 如果使用localhost，尝试构建localhost URL
    test_url = http_url
    if use_localhost:
        try:
            # 从公网URL中提取路径部分
            from urllib.parse import urlparse
            parsed = urlparse(http_url)
            path = parsed.path  # 例如: /outputs/2/59/1766938103378_clean.wav
            # 构建localhost URL（假设后端运行在8000端口）
            test_url = f"http://localhost:8000{path}"
            logger.info(f"使用localhost URL进行验证: {test_url}")
        except Exception as e:
            logger.warning(f"构建localhost URL失败，使用原始URL: {str(e)}")
            test_url = http_url
    
    for attempt in range(max_retries):
        try:
            # 发送HEAD请求检查文件是否存在（更轻量）
            try:
                response = requests.head(test_url, timeout=timeout, allow_redirects=True)
                if response.status_code == 200:
                    # 验证Content-Length，确保文件不为空
                    content_length = response.headers.get('Content-Length')
                    if content_length and int(content_length) > 0:
                        logger.info(f"文件已验证可通过HTTP访问 (尝试 {attempt + 1}/{max_retries}): {test_url}")
                        return True
                    else:
                        logger.warning(f"文件大小为0 (尝试 {attempt + 1}/{max_retries}): {test_url}")
                elif response.status_code == 403:
                    # 403可能是反向代理的限制，但如果使用localhost验证，说明FastAPI可以访问
                    if use_localhost and test_url.startswith("http://localhost"):
                        logger.info(f"localhost验证通过（403可能是反向代理限制，但FastAPI可以访问）: {test_url}")
                        return True
                    else:
                        logger.warning(f"HTTP 403 Forbidden (尝试 {attempt + 1}/{max_retries}): {test_url}")
                        logger.warning("这可能是权限问题，已尝试设置目录执行权限")
                elif response.status_code == 404:
                    logger.warning(f"文件未找到 (尝试 {attempt + 1}/{max_retries}): {test_url}")
                else:
                    logger.warning(f"HTTP状态码异常: {response.status_code} (尝试 {attempt + 1}/{max_retries}): {test_url}")
            except requests.exceptions.Timeout:
                logger.warning(f"HTTP请求超时 (尝试 {attempt + 1}/{max_retries}): {http_url}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"HTTP请求失败: {str(e)} (尝试 {attempt + 1}/{max_retries}): {http_url}")
            
            # 如果失败且还有重试机会，等待后重试
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"文件无法通过HTTP访问（已重试 {max_retries} 次）: {http_url}")
                return False
                
        except Exception as e:
            logger.warning(f"验证HTTP访问时出错 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return False
    
    return False


class CharacterRequest(BaseModel):
    """创建角色请求"""

    name: str = Field(
        ..., min_length=2, max_length=6, description="角色名称，2-6个字符"
    )
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
                    
                    # 关键：确保新创建的目录有执行权限，否则无法通过HTTP访问文件
                    # 设置目录权限：rwxr-xr-x (755)
                    os.chmod(user_role_dir, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                    
                    # 确保父目录也有执行权限
                    parent_dir = os.path.dirname(user_role_dir)
                    if os.path.exists(parent_dir):
                        os.chmod(parent_dir, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                    
                    logger.info(f"创建用户角色目录: {user_role_dir}")

                    # 获取文件名（应该已经是wav格式，因为上传时已转换）
                    file_name = file_record.get("file_name", "")

                    # 如果文件名为空或不是wav格式，尝试从file_url提取
                    if not file_name or not file_name.endswith(".wav"):
                        file_url = file_record.get("file_url", "")
                        if file_url:
                            # 从URL中提取文件名
                            file_name = os.path.basename(file_url)
                        else:
                            # 如果都没有，使用file_id生成文件名
                            file_name = f"{file_id}.wav"

                    # 确保文件名是wav格式
                    if not file_name.endswith(".wav"):
                        file_name = f"{os.path.splitext(file_name)[0]}.wav"

                    # 构建完整的文件路径（存储在outputs/{user_id}/{role_id}/目录下）
                    init_input = os.path.join(user_role_dir, file_name)
                    init_input = os.path.abspath(init_input)

                    # 如果原始文件不在目标目录，需要移动或复制
                    original_file_path = os.path.join(OUTPUTS_DIR, file_name)
                    if os.path.exists(original_file_path) and original_file_path != init_input:
                        # 如果目标文件已存在，先删除
                        if os.path.exists(init_input):
                            os.remove(init_input)
                        shutil.move(original_file_path, init_input)
                        logger.info(f"已移动文件到用户目录: {init_input}")

                    # 验证文件是否存在
                    if not os.path.exists(init_input):
                        logger.warning(
                            f"音频文件不存在: {init_input}，但仍保存记录到数据库"
                        )
                        # 插入记录，所有音频字段为 None
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
                            # 指定输出路径到用户目录
                            base_name = os.path.splitext(file_name)[0]
                            clean_output_path = os.path.join(
                                user_role_dir, f"{base_name}_clean.wav"
                            )
                            clean_output_path = os.path.abspath(clean_output_path)

                            clean_input_path = process_audio_with_deepfilternet_denoiser(
                                input_path=init_input,
                                output_path=clean_output_path,
                                device=None,  # 自动选择设备
                            )
                            if clean_input_path:
                                # 确保路径是绝对路径
                                clean_input_path = os.path.abspath(clean_input_path)
                                logger.info(f"音频降噪成功: {clean_input_path}")
                                
                                # 确保文件可以被HTTP访问（重要：解决文件系统同步延迟问题）
                                logger.info("验证降噪音频文件可访问性...")
                                if ensure_file_accessible(clean_input_path):
                                    logger.info("降噪音频文件已验证可访问，可以用于后续步骤")
                                else:
                                    logger.warning("降噪音频文件验证失败，但继续处理")
                            else:
                                logger.warning("音频降噪失败，跳过后续克隆步骤")
                        except Exception as e:
                            logger.error(f"音频降噪异常: {str(e)}")
                            clean_input_path = None

                        # 固定文本（用于 CosyVoice 和 AutoVoiceCloner）
                        fixed_text = "小朋友们大家好，这是一段黄金母本的音频，这段音频的主要目的呀，是为后续的所有音频克隆提供一段完美的音频输入"

                        # 步骤2: 使用 CosyVoice V3 进行声音克隆（新增）
                        cosy_voice_path = None
                        if clean_input_path and os.path.exists(clean_input_path):
                            logger.info(
                                f"步骤2: 开始 CosyVoice V3 克隆，input_audio={clean_input_path}"
                            )
                            try:
                                # 获取公网基础URL
                                public_base_url = os.getenv("PUBLIC_BASE_URL")
                                if not public_base_url:
                                    logger.warning(
                                        "PUBLIC_BASE_URL 未配置，跳过 CosyVoice V3 处理"
                                    )
                                else:
                                    # 在构建URL之前，再次确保文件可访问
                                    logger.info("在构建CosyVoice URL之前，再次验证文件可访问性...")
                                    if not ensure_file_accessible(clean_input_path, max_retries=3, retry_delay=0.3):
                                        logger.warning("文件验证失败，但继续尝试使用URL")
                                    
                                    # 添加短暂延迟，确保文件系统完全同步
                                    time.sleep(0.5)
                                    
                                    # 构建公网可访问的音频URL
                                    # 路径格式: /outputs/{user_id}/{role_id}/{文件名}
                                    clean_file_name = os.path.basename(clean_input_path)
                                    audio_url = f"{public_base_url.rstrip('/')}/outputs/{user_id}/{role_id}/{clean_file_name}"
                                    logger.info(f"CosyVoice 音频URL: {audio_url}")
                                    
                                    # 验证文件大小，确保文件已完全写入
                                    try:
                                        file_size = os.path.getsize(clean_input_path)
                                        logger.info(f"音频文件大小: {file_size} bytes")
                                        if file_size == 0:
                                            logger.error("音频文件大小为0，可能未完全写入")
                                            raise ValueError("音频文件大小为0")
                                    except Exception as e:
                                        logger.error(f"验证文件大小时出错: {str(e)}")
                                    
                                    # 关键：通过HTTP请求验证文件是否真的可以通过URL访问
                                    # 这确保FastAPI的StaticFiles已经识别到新文件
                                    logger.info("通过HTTP请求验证文件可访问性...")
                                    if not ensure_file_accessible_via_http(clean_input_path, audio_url, max_retries=10, retry_delay=1.0):
                                        logger.error(f"文件无法通过HTTP访问，但继续尝试: {audio_url}")
                                        # 即使验证失败，也继续尝试，因为可能是网络问题
                                    else:
                                        logger.info("文件已验证可通过HTTP访问，可以安全使用")
                                    
                                    # 指定输出路径
                                    cosy_output_path = os.path.join(
                                        user_role_dir, f"{base_name}_cosyvoice.mp3"
                                    )
                                    cosy_output_path = os.path.abspath(cosy_output_path)

                                    # 初始化 CosyVoiceV3 客户端
                                    cosy_voice_client = CosyVoiceV3()

                                    # 执行 CosyVoice V3 克隆
                                    cosy_voice_client.synthesize(
                                        audio_url=audio_url,
                                        text_to_synthesize=fixed_text,
                                        output_file=cosy_output_path,
                                    )

                                    # 验证输出文件是否存在
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
                        # 优先使用 cosy_voice_path，如果不存在则使用 clean_input_path
                        input_for_cloning = cosy_voice_path if cosy_voice_path and os.path.exists(cosy_voice_path) else clean_input_path

                        if input_for_cloning and os.path.exists(input_for_cloning):
                            logger.info(
                                f"步骤3: 开始 AutoVoiceCloner 克隆，input_audio={input_for_cloning}"
                            )
                            try:
                                # 验证 Golden Master Prompt 文件是否存在
                                if not os.path.exists(GOLDEN_MASTER_PROMPT):
                                    logger.error(
                                        f"Golden Master Prompt 文件不存在: {GOLDEN_MASTER_PROMPT}"
                                    )
                                    tts_voice_path = None
                                else:
                                    # 初始化 AutoVoiceCloner，指定输出目录为用户目录
                                    voice_cloner = AutoVoiceCloner(
                                        output_dir=user_role_dir
                                    )

                                    # 执行单条克隆（使用情绪音频引导模式）
                                    clone_result = voice_cloner.run_cloning(
                                        input_audio=input_for_cloning,  # 优先使用 CosyVoice 结果，否则使用降噪音频
                                        emo_audio=GOLDEN_MASTER_PROMPT,  # Golden Master Prompt 作为情感引导
                                        emo_text=fixed_text,  # 默认文本
                                    )

                                    # 检查克隆是否成功
                                    if clone_result.get(
                                        "success"
                                    ) > 0 and clone_result.get("results"):
                                        cloned_path = clone_result["results"][0].get(
                                            "output_path"
                                        )
                                        if cloned_path and os.path.exists(cloned_path):
                                            tts_voice_path = os.path.abspath(cloned_path)
                                            logger.info(f"AutoVoiceCloner 克隆成功: {tts_voice_path}")
                                        else:
                                            logger.warning("AutoVoiceCloner 克隆失败，输出文件不存在")
                                    else:
                                        error_msg = clone_result.get("results", [{}])[
                                            0
                                        ].get("error", "未知错误")
                                        logger.warning(
                                            f"AutoVoiceCloner 克隆失败: {error_msg}"
                                        )
                            except Exception as e:
                                logger.error(f"AutoVoiceCloner 克隆异常: {str(e)}")
                                tts_voice_path = None
                        else:
                            logger.warning("输入音频不可用，跳过 AutoVoiceCloner 处理")

                        # 插入记录，包含所有4个音频路径
                        user_input_audio_dao.insert(
                            user_id=user_id,
                            role_id=role_id,
                            init_input=init_input,
                            clean_input=clean_input_path,
                            cosy_voice=cosy_voice_path,
                            tts_voice=tts_voice_path,
                        )
                        logger.info(
                            f"已保存录音到user_input_audio表: user_id={user_id}, role_id={role_id}, "
                            f"file_id={file_id}, init_input={init_input}, clean_input={clean_input_path}, "
                            f"cosy_voice={cosy_voice_path}, tts_voice={tts_voice_path}"
                        )
            except (ValueError, Exception) as e:
                logger.warning(f"保存录音到user_input_audio表失败: {str(e)}")
                # 即使保存失败，也不影响角色创建
        role = character_dao.find_by_id(role_id)
        if not role:
            raise HTTPException(status_code=500, detail="角色创建失败")

        return CharacterResponse(
            id=str(role["id"]),
            name=role["role_name"],
            createdAt=role["create_time"].isoformat()
            if role.get("create_time")
            else "",
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
                createdAt=char["create_time"].isoformat()
                if char.get("create_time")
                else "",
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

        # 验证角色是否存在
        character = character_dao.find_by_id(character_id)
        if not character:
            raise HTTPException(status_code=404, detail="角色不存在")

        # 验证角色是否属于当前用户
        if not character_dao.belongs_to_user(character_id, user_id):
            raise HTTPException(status_code=403, detail="无权访问该角色")

        # 查询角色的音频信息
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
