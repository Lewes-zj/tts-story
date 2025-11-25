"""文件管理API"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import uuid
import time
from scripts.file_dao import FileDAO
from scripts.auth_api import get_current_user
import logging

logger = logging.getLogger(__name__)

# 尝试导入pydub用于音频格式转换
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub库未安装，无法进行音频格式转换")

# 检查ffmpeg/ffprobe是否可用
def check_ffmpeg_available():
    """检查ffmpeg/ffprobe是否可用"""
    import shutil
    # 检查ffprobe（pydub使用ffprobe来检测音频格式）
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path:
        return True, ffprobe_path
    return False, None

FFMPEG_AVAILABLE, FFPROBE_PATH = check_ffmpeg_available()
if not FFMPEG_AVAILABLE:
    logger.warning("ffmpeg/ffprobe未安装，webm格式转换将不可用")
router = APIRouter(prefix="/api/files", tags=["文件管理"])

# 创建DAO实例
file_dao = FileDAO()

# 文件上传配置
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/tts-story/uploads")
OUTPUTS_DIR = "outputs"
FILE_URL_PREFIX = os.getenv("FILE_URL_PREFIX", "http://localhost:8080/api/files/audio/")


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    id: str
    url: str
    name: str


# 确保上传目录和输出目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """上传录音文件，自动转换为wav格式"""
    try:
        user_id = current_user["user_id"]
        
        # 读取文件内容
        content = await file.read()
        if not content or len(content) == 0:
            raise HTTPException(status_code=400, detail="上传的文件为空")
        
        original_filename = file.filename or "recording"
        file_extension = os.path.splitext(original_filename)[1].lower()
        
        logger.info(f"开始上传文件: {original_filename}, 扩展名: {file_extension}, 大小: {len(content)} bytes, PYDUB_AVAILABLE: {PYDUB_AVAILABLE}")
        
        # 生成唯一文件名（wav格式，使用时间戳，与audio_tts.py保持一致）
        unique_filename = f"{int(time.time() * 1000)}.wav"
        wav_file_path = os.path.join(OUTPUTS_DIR, unique_filename)
        
        # 如果上传的是webm或其他格式，转换为wav
        if file_extension in ['.webm', '.ogg', '.mp3', '.m4a']:
            if not PYDUB_AVAILABLE:
                # pydub不可用，返回错误提示
                raise HTTPException(
                    status_code=500,
                    detail="音频格式转换功能不可用，请安装pydub库: pip install pydub"
                )
            
            # 检查webm格式是否需要ffmpeg
            if file_extension == '.webm' and not FFMPEG_AVAILABLE:
                raise HTTPException(
                    status_code=500,
                    detail="webm格式转换需要ffmpeg支持。请安装ffmpeg:\n"
                           "Ubuntu/Debian: sudo apt-get install ffmpeg\n"
                           "CentOS/RHEL: sudo yum install ffmpeg\n"
                           "macOS: brew install ffmpeg\n"
                           "Windows: 下载并安装 https://ffmpeg.org/download.html"
                )
            
            temp_file_path = None
            try:
                # 先保存原始文件到临时位置
                temp_file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{file_extension}")
                with open(temp_file_path, "wb") as f:
                    f.write(content)
                
                # 使用pydub转换为wav
                try:
                    # 尝试指定格式读取
                    audio = AudioSegment.from_file(temp_file_path, format=file_extension[1:])
                except Exception as format_error:
                    # 如果格式识别失败，尝试不指定格式让pydub自动识别
                    logger.warning(f"指定格式读取失败，尝试自动识别: {str(format_error)}")
                    try:
                        audio = AudioSegment.from_file(temp_file_path)
                    except Exception as auto_error:
                        # 如果自动识别也失败，检查是否是ffmpeg问题
                        error_str = str(auto_error).lower()
                        if 'ffprobe' in error_str or 'ffmpeg' in error_str:
                            raise HTTPException(
                                status_code=500,
                                detail="音频格式转换失败，需要ffmpeg支持。请安装ffmpeg:\n"
                                       "Ubuntu/Debian: sudo apt-get install ffmpeg\n"
                                       "CentOS/RHEL: sudo yum install ffmpeg\n"
                                       "macOS: brew install ffmpeg\n"
                                       "Windows: 下载并安装 https://ffmpeg.org/download.html"
                            )
                        raise
                
                audio.export(wav_file_path, format="wav")
                
                # 更新文件大小
                content_size = os.path.getsize(wav_file_path)
                logger.info(f"音频已转换为wav格式: {original_filename} -> {unique_filename}")
            except HTTPException:
                # 重新抛出HTTP异常
                raise
            except Exception as e:
                logger.error(f"音频格式转换失败: {str(e)}")
                # 清理临时文件
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except:
                        pass
                # 转换失败，抛出错误
                error_str = str(e).lower()
                if 'ffprobe' in error_str or 'ffmpeg' in error_str:
                    raise HTTPException(
                        status_code=500, 
                        detail="音频格式转换失败，需要ffmpeg支持。请安装ffmpeg:\n"
                               "Ubuntu/Debian: sudo apt-get install ffmpeg\n"
                               "CentOS/RHEL: sudo yum install ffmpeg\n"
                               "macOS: brew install ffmpeg\n"
                               "Windows: 下载并安装 https://ffmpeg.org/download.html"
                    )
                else:
                    raise HTTPException(
                        status_code=500, 
                        detail=f"音频格式转换失败: {str(e)}"
                    )
        elif file_extension == '.wav':
            # 如果已经是wav格式，直接保存
            with open(wav_file_path, "wb") as f:
                f.write(content)
            content_size = len(content)
        elif not file_extension:
            # 没有扩展名，尝试作为webm处理（浏览器录音通常是webm）
            logger.warning(f"文件没有扩展名，尝试作为webm格式处理: {original_filename}")
            if PYDUB_AVAILABLE:
                temp_file_path = None
                try:
                    temp_file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.webm")
                    with open(temp_file_path, "wb") as f:
                        f.write(content)
                    
                    # 尝试自动识别格式
                    audio = AudioSegment.from_file(temp_file_path)
                    audio.export(wav_file_path, format="wav")
                    
                    content_size = os.path.getsize(wav_file_path)
                    logger.info(f"音频已转换为wav格式（无扩展名）: {original_filename} -> {unique_filename}")
                except Exception as e:
                    logger.error(f"音频格式转换失败: {str(e)}")
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.remove(temp_file_path)
                        except:
                            pass
                    raise HTTPException(
                        status_code=500,
                        detail=f"音频格式转换失败: {str(e)}"
                    )
            else:
                raise HTTPException(
                    status_code=500,
                    detail="音频格式转换功能不可用，请安装pydub库和ffmpeg"
                )
        else:
            # 不支持其他格式，返回错误
            raise HTTPException(status_code=400, detail=f"不支持的音频格式: {file_extension}，请使用webm或wav格式")
        
        # 保存文件信息到数据库
        file_url = f"{FILE_URL_PREFIX}{unique_filename}"
        file_id = file_dao.insert(
            user_id=user_id,
            file_name=unique_filename,  # 使用转换后的wav文件名
            file_url=file_url,
            file_type="audio/wav",
            file_size=content_size
        )
        
        # 更新URL为使用ID
        actual_url = f"{FILE_URL_PREFIX}{file_id}"
        
        return FileUploadResponse(
            id=str(file_id),
            url=actual_url,
            name=unique_filename
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.get("/audio/{file_id}")
async def get_audio_file(file_id: int):
    """获取音频文件"""
    try:
        file_record = file_dao.find_by_id(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 从file_url中提取文件名，或使用file_name
        # 这里简化处理，实际应该存储完整的文件路径
        file_name = file_record["file_name"]
        file_path = os.path.join(OUTPUTS_DIR, file_name)
        
        # 如果直接文件名不存在，尝试查找UUID格式的文件
        if not os.path.exists(file_path):
            # 尝试通过file_id查找（如果文件名是UUID格式）
            # 这里简化处理，实际应该存储完整的文件路径
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return FileResponse(
            path=file_path,
            media_type="audio/wav",
            filename=file_record["file_name"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取音频文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取音频文件失败: {str(e)}")

