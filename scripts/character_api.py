"""角色管理API"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import logging
import shutil
import time
import stat
import subprocess
from concurrent.futures import ThreadPoolExecutor
from scripts.character_dao import CharacterDAO
from scripts.user_input_audio_dao import UserInputAudioDAO
from scripts.file_dao import FileDAO
from scripts.auth_api import get_current_user
from scripts.audio_processor import process_audio_with_deepfilternet_denoiser
from scripts.auto_voice_cloner import AutoVoiceCloner
from scripts.cosyvoice_v3 import CosyVoiceV3

logger = logging.getLogger(__name__)

# 创建线程池执行器用于后台任务（角色声音克隆）
# 使用单独的线程池，避免与音频生成任务竞争资源
character_clone_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="character_clone_")

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
            
            # 强制刷新文件系统和目录缓存
            parent_dir = os.path.dirname(file_path)
            
            # 方法1: 多次访问文件，强制刷新inode缓存
            for _ in range(3):
                try:
                    with open(file_path, 'rb') as f:
                        f.read(1)
                        os.fsync(f.fileno())
                except Exception:
                    pass
            
            # 方法2: 列出目录内容，强制刷新目录dentry缓存
            # 这是关键：os.listdir()会强制文件系统重新扫描目录
            try:
                if os.path.exists(parent_dir):
                    os.listdir(parent_dir)  # 强制刷新目录缓存
                    logger.debug(f"已刷新目录缓存: {parent_dir}")
            except Exception as e:
                logger.debug(f"刷新目录缓存失败: {str(e)}")
            
            # 方法3: 更新父目录mtime
            try:
                if os.path.exists(parent_dir):
                    os.utime(parent_dir, None)
                    logger.debug(f"已更新父目录mtime: {parent_dir}")
            except Exception:
                pass
            
            # 方法4: 使用stat系统调用多次访问文件，确保inode已更新
            try:
                for _ in range(3):
                    os.stat(file_path)
            except Exception:
                pass
            
            # 方法5: 强制同步文件系统
            try:
                os.sync()
            except Exception:
                pass
            
            # 方法6: 使用系统命令强制刷新（最激进的方法）
            # 通过subprocess调用sync命令，确保所有挂起的写入都已刷新到磁盘
            try:
                subprocess.run(['sync'], check=False, timeout=5, 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.debug("已执行系统sync命令")
            except Exception:
                pass
            
            # 方法7: 使用find命令访问文件，强制文件系统识别新文件
            # 这可以触发文件系统的dentry缓存更新
            try:
                subprocess.run(['find', parent_dir, '-name', os.path.basename(file_path), 
                              '-type', 'f', '-exec', 'true', '{}', ';'],
                             check=False, timeout=5,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.debug("已使用find命令访问文件，刷新dentry缓存")
            except Exception:
                pass
            
            # 方法8: 使用ls命令列出目录，强制文件系统重新扫描目录
            # 这是最直接的方法，可以强制刷新目录的dentry缓存
            try:
                subprocess.run(['ls', '-la', parent_dir],
                             check=False, timeout=5,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.debug("已使用ls命令列出目录，强制刷新dentry缓存")
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


def process_character_voice_cloning(
    user_id: int,
    role_id: int,
    clean_input_path: str,
    user_role_dir: str,
    base_name: str,
    init_input: str
):
    """
    后台任务：处理角色声音克隆（步骤2和步骤3）
    
    Args:
        user_id: 用户ID
        role_id: 角色ID
        clean_input_path: 降噪后的音频文件路径
        user_role_dir: 用户角色目录
        base_name: 文件基础名称（不含扩展名）
        init_input: 初始输入文件路径
    """
    logger.info("=" * 70)
    logger.info("🎬 [后台任务] 开始处理角色声音克隆")
    logger.info(f"   用户ID: {user_id}")
    logger.info(f"   角色ID: {role_id}")
    logger.info(f"   降噪音频路径: {clean_input_path}")
    logger.info(f"   工作目录: {user_role_dir}")
    logger.info("=" * 70)
    
    fixed_text = "小朋友们大家好，这是一段黄金母本的音频，这段音频的主要目的呀，是为后续的所有音频克隆提供一段完美的音频输入"
    
    cosy_voice_path = None
    tts_voice_path = None
    
    try:
        # 步骤2: 使用 CosyVoice V3 进行声音克隆
        logger.info("-" * 70)
        logger.info("📝 [步骤2] 开始 CosyVoice V3 声音克隆")
        logger.info("-" * 70)
        
        if clean_input_path and os.path.exists(clean_input_path):
            logger.info(f"✓ 降噪音频文件存在: {clean_input_path}")
            file_size = os.path.getsize(clean_input_path)
            logger.info(f"  文件大小: {file_size} bytes")
            
            try:
                public_base_url = os.getenv("PUBLIC_BASE_URL")
                if not public_base_url:
                    logger.warning("⚠️ PUBLIC_BASE_URL 未配置，跳过 CosyVoice V3 处理")
                else:
                    logger.info(f"✓ PUBLIC_BASE_URL 已配置: {public_base_url}")
                    
                    # 等待一段时间，确保文件系统完全同步
                    logger.info("⏳ 等待文件系统完全同步（10秒）...")
                    time.sleep(10.0)
                    logger.info("✓ 文件系统同步等待完成")
                    
                    clean_file_name = os.path.basename(clean_input_path)
                    audio_url = f"{public_base_url.rstrip('/')}/outputs/{user_id}/{role_id}/{clean_file_name}"
                    logger.info(f"📡 构造音频URL: {audio_url}")
                    
                    cosy_output_path = os.path.join(user_role_dir, f"{base_name}_cosyvoice.mp3")
                    cosy_output_path = os.path.abspath(cosy_output_path)
                    logger.info(f"📁 输出文件路径: {cosy_output_path}")

                    logger.info("🔄 正在调用 CosyVoice V3 API 进行声音克隆...")
                    
                    # 添加重试机制，处理 WebSocket 连接问题
                    max_retries = 3
                    retry_delay = 5.0  # 重试前等待5秒
                    cosy_voice_client = CosyVoiceV3()
                    
                    for retry_count in range(max_retries):
                        try:
                            logger.info(f"   尝试 {retry_count + 1}/{max_retries}...")
                            cosy_voice_client.synthesize(
                                audio_url=audio_url,
                                text_to_synthesize=fixed_text,
                                output_file=cosy_output_path,
                            )
                            logger.info("✓ CosyVoice V3 API 调用完成")
                            break  # 成功则跳出重试循环
                        except TimeoutError as e:
                            error_msg = str(e)
                            logger.warning(f"⚠️ CosyVoice V3 WebSocket 连接超时 (尝试 {retry_count + 1}/{max_retries})")
                            logger.warning(f"   错误信息: {error_msg}")
                            
                            if retry_count < max_retries - 1:
                                logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                                time.sleep(retry_delay)
                                # 每次重试前增加等待时间
                                retry_delay *= 1.5
                            else:
                                logger.error("❌ CosyVoice V3 所有重试均失败，WebSocket 连接无法建立")
                                logger.error("   可能原因：网络环境限制、防火墙阻止、代理配置问题")
                                logger.error("   将跳过步骤2，直接使用降噪音频进行步骤3")
                                raise
                        except Exception as e:
                            error_msg = str(e)
                            error_type = type(e).__name__
                            logger.warning(f"⚠️ CosyVoice V3 调用异常 (尝试 {retry_count + 1}/{max_retries}): {error_type}")
                            logger.warning(f"   错误信息: {error_msg}")
                            
                            # 如果是 WebSocket 相关错误，进行重试
                            if "websocket" in error_msg.lower() or "connection" in error_msg.lower():
                                if retry_count < max_retries - 1:
                                    logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                                    time.sleep(retry_delay)
                                    retry_delay *= 1.5
                                else:
                                    logger.error("❌ CosyVoice V3 所有重试均失败")
                                    logger.error("   将跳过步骤2，直接使用降噪音频进行步骤3")
                                    raise
                            else:
                                # 其他类型的错误，直接抛出
                                logger.error(f"❌ CosyVoice V3 调用失败: {error_type}")
                                raise

                    if os.path.exists(cosy_output_path):
                        cosy_voice_path = cosy_output_path
                        output_size = os.path.getsize(cosy_output_path)
                        logger.info("✅ [步骤2] CosyVoice V3 克隆成功!")
                        logger.info(f"   输出文件: {cosy_voice_path}")
                        logger.info(f"   文件大小: {output_size} bytes")
                        
                        # 更新数据库中的 cosy_voice 字段
                        logger.info("💾 正在更新数据库 cosy_voice 字段...")
                        update_success = user_input_audio_dao.update_cosy_voice(user_id, role_id, cosy_voice_path)
                        if update_success:
                            logger.info(f"✅ 数据库更新成功: cosy_voice={cosy_voice_path}")
                        else:
                            logger.warning("⚠️ 数据库更新失败，但文件已生成")
                    else:
                        logger.error("❌ [步骤2] CosyVoice V3 克隆失败: 输出文件不存在")
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                logger.error("❌ [步骤2] CosyVoice V3 克隆异常")
                logger.error(f"   异常类型: {error_type}")
                logger.error(f"   错误信息: {error_msg}")
                
                # 如果是 WebSocket 连接问题，记录更详细的诊断信息
                if "websocket" in error_msg.lower() or "connection" in error_msg.lower():
                    logger.error("   诊断信息:")
                    logger.error("   - 检查网络连接是否正常")
                    logger.error("   - 检查防火墙是否阻止 WebSocket 连接")
                    logger.error("   - 检查代理配置是否正确")
                    logger.error("   - 检查 PUBLIC_BASE_URL 是否可访问")
                    logger.error(f"   - 音频URL: {audio_url}")
                
                logger.error("   将跳过步骤2，直接使用降噪音频进行步骤3")
                logger.error("", exc_info=True)
                cosy_voice_path = None
        else:
            logger.warning("⚠️ [步骤2] 降噪音频不可用，跳过 CosyVoice V3 处理")
            logger.warning(f"   文件路径: {clean_input_path}")
            logger.warning(f"   文件存在: {os.path.exists(clean_input_path) if clean_input_path else False}")

        # 步骤3: 使用 AutoVoiceCloner 进行最终声音克隆
        logger.info("-" * 70)
        logger.info("📝 [步骤3] 开始 AutoVoiceCloner 最终声音克隆")
        logger.info("-" * 70)
        
        input_for_cloning = cosy_voice_path if cosy_voice_path and os.path.exists(cosy_voice_path) else clean_input_path
        logger.info(f"📥 选择输入音频: {input_for_cloning}")
        logger.info(f"   来源: {'CosyVoice V3 输出' if cosy_voice_path and os.path.exists(cosy_voice_path) else '降噪音频'}")

        if input_for_cloning and os.path.exists(input_for_cloning):
            logger.info(f"✓ 输入音频文件存在: {input_for_cloning}")
            input_size = os.path.getsize(input_for_cloning)
            logger.info(f"  文件大小: {input_size} bytes")
            
            try:
                if not os.path.exists(GOLDEN_MASTER_PROMPT):
                    logger.error(f"❌ [步骤3] Golden Master Prompt 文件不存在: {GOLDEN_MASTER_PROMPT}")
                    tts_voice_path = None
                else:
                    logger.info(f"✓ Golden Master Prompt 文件存在: {GOLDEN_MASTER_PROMPT}")
                    logger.info("🔄 正在调用 AutoVoiceCloner 进行声音克隆...")
                    
                    voice_cloner = AutoVoiceCloner(output_dir=user_role_dir)
                    clone_result = voice_cloner.run_cloning(
                        input_audio=input_for_cloning,
                        emo_audio=GOLDEN_MASTER_PROMPT,
                        emo_text=fixed_text,
                    )
                    logger.info("✓ AutoVoiceCloner API 调用完成")

                    if clone_result.get("success") > 0 and clone_result.get("results"):
                        cloned_path = clone_result["results"][0].get("output_path")
                        if cloned_path and os.path.exists(cloned_path):
                            tts_voice_path = os.path.abspath(cloned_path)
                            output_size = os.path.getsize(tts_voice_path)
                            logger.info("✅ [步骤3] AutoVoiceCloner 克隆成功!")
                            logger.info(f"   输出文件: {tts_voice_path}")
                            logger.info(f"   文件大小: {output_size} bytes")
                            
                            # 更新数据库中的 tts_voice 字段
                            logger.info("💾 正在更新数据库 tts_voice 字段...")
                            update_success = user_input_audio_dao.update_tts_voice(user_id, role_id, tts_voice_path)
                            if update_success:
                                logger.info(f"✅ 数据库更新成功: tts_voice={tts_voice_path}")
                            else:
                                logger.warning("⚠️ 数据库更新失败，但文件已生成")
                        else:
                            logger.error("❌ [步骤3] AutoVoiceCloner 克隆失败: 输出文件不存在")
                            logger.error(f"   预期路径: {cloned_path}")
                    else:
                        error_msg = clone_result.get("results", [{}])[0].get("error", "未知错误")
                        logger.error(f"❌ [步骤3] AutoVoiceCloner 克隆失败: {error_msg}")
            except Exception as e:
                logger.error(f"❌ [步骤3] AutoVoiceCloner 克隆异常: {str(e)}", exc_info=True)
                tts_voice_path = None
        else:
            logger.warning("⚠️ [步骤3] 输入音频不可用，跳过 AutoVoiceCloner 处理")
            logger.warning(f"   文件路径: {input_for_cloning}")
            logger.warning(f"   文件存在: {os.path.exists(input_for_cloning) if input_for_cloning else False}")
        
        # 任务完成总结
        logger.info("=" * 70)
        logger.info("🎉 [后台任务] 角色声音克隆处理完成")
        logger.info(f"   用户ID: {user_id}")
        logger.info(f"   角色ID: {role_id}")
        logger.info(f"   步骤2 (CosyVoice V3): {'✅ 成功' if cosy_voice_path else '❌ 失败'}")
        logger.info(f"   步骤3 (AutoVoiceCloner): {'✅ 成功' if tts_voice_path else '❌ 失败'}")
        if cosy_voice_path:
            logger.info(f"   CosyVoice 输出: {cosy_voice_path}")
        if tts_voice_path:
            logger.info(f"   TTS Voice 输出: {tts_voice_path}")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error("=" * 70)
        logger.error("💥 [后台任务] 角色声音克隆处理异常")
        logger.error(f"   用户ID: {user_id}")
        logger.error(f"   角色ID: {role_id}")
        logger.error(f"   异常信息: {str(e)}")
        logger.error("=" * 70, exc_info=True)


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
                                
                                # 强制刷新文件系统和目录缓存，确保FastAPI StaticFiles能够识别新文件
                                logger.info("强制刷新文件系统和目录缓存，确保FastAPI StaticFiles能够识别新文件...")
                                ensure_file_accessible(clean_input_path)
                                
                                # 验证文件确实存在且可读
                                if os.path.exists(clean_input_path) and os.access(clean_input_path, os.R_OK):
                                    file_size = os.path.getsize(clean_input_path)
                                    logger.info(f"文件验证通过: {clean_input_path}, 大小: {file_size} bytes")
                                else:
                                    logger.warning(f"文件验证失败: {clean_input_path}")
                                
                                logger.info("文件系统和目录缓存已刷新，文件应该可以通过HTTP访问")
                            else:
                                logger.warning("音频降噪失败，跳过后续克隆步骤")
                        except Exception as e:
                            logger.error(f"音频降噪异常: {str(e)}")
                            clean_input_path = None

                        # 先插入记录，包含步骤1的结果（clean_input）
                        # 步骤2和步骤3将在后台任务中完成并更新
                        user_input_audio_dao.insert(
                            user_id=user_id,
                            role_id=role_id,
                            init_input=init_input,
                            clean_input=clean_input_path,
                            cosy_voice=None,  # 将在后台任务中更新
                            tts_voice=None,  # 将在后台任务中更新
                        )
                        logger.info(f"已保存录音到user_input_audio表: role_id={role_id}")

                        # 如果步骤1成功，将步骤2和步骤3提交到后台任务队列
                        if clean_input_path and os.path.exists(clean_input_path):
                            logger.info("-" * 70)
                            logger.info("🚀 将步骤2和步骤3提交到后台任务队列")
                            logger.info(f"   角色ID: {role_id}")
                            logger.info(f"   降噪音频: {clean_input_path}")
                            logger.info("-" * 70)
                            
                            character_clone_executor.submit(
                                process_character_voice_cloning,
                                user_id=user_id,
                                role_id=role_id,
                                clean_input_path=clean_input_path,
                                user_role_dir=user_role_dir,
                                base_name=base_name,
                                init_input=init_input
                            )
                            
                            logger.info(f"✅ 后台任务已成功提交到线程池: role_id={role_id}")
                            logger.info("   任务将在后台异步执行步骤2 (CosyVoice V3) 和步骤3 (AutoVoiceCloner)")
                        else:
                            logger.warning("⚠️ 步骤1失败，跳过后台任务提交")
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