"""阿里云ASR语音识别API"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional
import os
import logging
import json
import base64
import time
import hmac
import hashlib
import urllib.parse
import requests
import yaml
from scripts.auth_api import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/asr", tags=["语音识别"])

# 阿里云ASR配置（从配置文件读取）
def load_asr_config():
    """加载阿里云ASR配置"""
    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config", "aliyun_asr.yaml")
        
        if not os.path.exists(config_path):
            logger.warning(f"ASR配置文件不存在: {config_path}")
            return {
                "access_key_id": "",
                "access_key_secret": "",
                "app_key": "",
                "endpoint": "https://nls-gateway.cn-shanghai.aliyuncs.com"
            }
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        asr_config = config.get("aliyun_asr", {})
        return {
            "access_key_id": asr_config.get("access_key_id", ""),
            "access_key_secret": asr_config.get("access_key_secret", ""),
            "app_key": asr_config.get("app_key", ""),
            "endpoint": asr_config.get("endpoint", "https://nls-gateway.cn-shanghai.aliyuncs.com")
        }
    except Exception as e:
        logger.error(f"加载ASR配置失败: {str(e)}", exc_info=True)
        return {
            "access_key_id": "",
            "access_key_secret": "",
            "app_key": "",
            "endpoint": "https://nls-gateway.cn-shanghai.aliyuncs.com"
        }

# 加载配置
_ASR_CONFIG = load_asr_config()
ALIYUN_ACCESS_KEY_ID = _ASR_CONFIG["access_key_id"]
ALIYUN_ACCESS_KEY_SECRET = _ASR_CONFIG["access_key_secret"]
ALIYUN_ASR_APP_KEY = _ASR_CONFIG["app_key"]
ALIYUN_ASR_ENDPOINT = _ASR_CONFIG["endpoint"]

# 检查配置
if not ALIYUN_ACCESS_KEY_ID or not ALIYUN_ACCESS_KEY_SECRET:
    logger.warning("阿里云ASR配置未设置，ASR功能将不可用。请在 config/aliyun_asr.yaml 中配置")


class ASRRequest(BaseModel):
    """ASR识别请求（使用文件ID）"""
    fileId: str
    expectedText: Optional[str] = None  # 期望的文本，用于验证


class ASRResponse(BaseModel):
    """ASR识别响应"""
    recognizedText: str
    confidence: Optional[float] = None
    validationPassed: bool  # 是否与期望文本匹配
    message: Optional[str] = None


class ASRDirectRequest(BaseModel):
    """ASR直接识别请求（上传音频文件）"""
    expectedText: Optional[str] = None  # 期望的文本，用于验证


def get_aliyun_token() -> str:
    """
    获取阿里云ASR Token
    参考: https://help.aliyun.com/document_detail/72138.html
    """
    if not ALIYUN_ACCESS_KEY_ID or not ALIYUN_ACCESS_KEY_SECRET:
        raise HTTPException(
            status_code=500,
            detail="阿里云ASR配置未设置，请联系管理员"
        )
    
    url = "https://nls-meta.cn-shanghai.aliyuncs.com/"
    params = {
        "AccessKeyId": ALIYUN_ACCESS_KEY_ID,
        "Action": "CreateToken",
        "Format": "JSON",
        "RegionId": "cn-shanghai",
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": str(int(time.time() * 1000)),
        "SignatureVersion": "1.0",
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "Version": "2019-02-28"
    }
    
    # 生成签名
    sorted_params = sorted(params.items())
    query_string = urllib.parse.urlencode(sorted_params)
    string_to_sign = f"GET&{urllib.parse.quote('/', safe='')}&{urllib.parse.quote(query_string, safe='')}"
    
    secret = f"{ALIYUN_ACCESS_KEY_SECRET}&"
    signature = base64.b64encode(
        hmac.new(secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).digest()
    ).decode('utf-8')
    
    params["Signature"] = signature
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if "Token" in result and "Id" in result["Token"]:
            return result["Token"]["Id"]
        else:
            logger.error(f"获取Token失败: {result}")
            raise HTTPException(status_code=500, detail="获取阿里云Token失败")
    except requests.RequestException as e:
        logger.error(f"请求Token时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取Token失败: {str(e)}")


def recognize_audio_file(audio_file_path: str, token: str) -> dict:
    """
    使用阿里云ASR识别音频文件
    
    Args:
        audio_file_path: 音频文件路径
        token: 阿里云Token
        
    Returns:
        识别结果字典，包含text和confidence
    """
    if not ALIYUN_ASR_APP_KEY:
        raise HTTPException(
            status_code=500,
            detail="阿里云ASR AppKey未设置，请联系管理员"
        )
    
    # 构建请求URL（使用正确的阿里云ASR端点）
    url = "https://nls-meta.cn-shanghai.aliyuncs.com/stream/v1/asr"
    
    # 构建请求头
    headers = {
        "X-Acw-Token": token
    }
    
    # 构建请求参数
    data = {
        "app_key": ALIYUN_ASR_APP_KEY,
        "format": "wav",  # 支持 wav, mp3, pcm 等
        "sample_rate": 16000,  # 采样率
    }
    
    try:
        # 读取音频文件并上传
        with open(audio_file_path, 'rb') as audio_file:
            files = {
                'audio': (os.path.basename(audio_file_path), audio_file, 'audio/wav')
            }
            
            response = requests.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=30
            )
        
        response.raise_for_status()
        result = response.json()
        
        # 解析识别结果
        # 阿里云ASR返回格式可能因版本而异，这里处理常见的格式
        if "result" in result:
            recognized_text = result["result"]
            confidence = result.get("confidence", 0.0)
        elif "text" in result:
            recognized_text = result["text"]
            confidence = result.get("confidence", 0.0)
        elif "data" in result and "result" in result["data"]:
            recognized_text = result["data"]["result"]
            confidence = result["data"].get("confidence", 0.0)
        else:
            logger.error(f"ASR识别返回格式异常: {result}")
            raise HTTPException(status_code=500, detail=f"识别失败: 返回格式异常")
        
        return {
            "text": recognized_text,
            "confidence": confidence
        }
            
    except requests.RequestException as e:
        logger.error(f"ASR请求失败: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                logger.error(f"错误详情: {error_detail}")
            except:
                logger.error(f"错误响应: {e.response.text}")
        raise HTTPException(status_code=500, detail=f"ASR请求失败: {str(e)}")


@router.post("/recognize", response_model=ASRResponse)
async def recognize_audio(
    file: UploadFile = File(...),
    expected_text: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    识别上传的音频文件
    
    Args:
        file: 音频文件（支持 wav, mp3, webm 等格式）
        expected_text: 期望的文本，用于验证识别结果是否匹配
        current_user: 当前用户（从token获取）
        
    Returns:
        ASRResponse: 识别结果
    """
    try:
        # 检查配置
        if not ALIYUN_ACCESS_KEY_ID or not ALIYUN_ACCESS_KEY_SECRET:
            raise HTTPException(
                status_code=500,
                detail="ASR服务未配置，请联系管理员"
            )
        
        # 读取上传的文件
        content = await file.read()
        if not content or len(content) == 0:
            raise HTTPException(status_code=400, detail="上传的文件为空")
        
        # 保存临时文件
        import tempfile
        import uuid
        
        file_extension = os.path.splitext(file.filename or "audio")[1].lower()
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_extension,
            prefix=f"asr_{uuid.uuid4().hex}_"
        )
        
        try:
            temp_file.write(content)
            temp_file.close()
            
            # 如果是webm等格式，需要转换为wav
            # 这里假设已经转换为wav，或者使用pydub转换
            audio_file_path = temp_file.name
            
            # 尝试转换音频格式（如果需要）
            try:
                from pydub import AudioSegment
                if file_extension in ['.webm', '.ogg', '.mp3', '.m4a']:
                    audio = AudioSegment.from_file(audio_file_path)
                    wav_file_path = audio_file_path.replace(file_extension, '.wav')
                    audio.export(wav_file_path, format="wav")
                    os.unlink(audio_file_path)  # 删除原文件
                    audio_file_path = wav_file_path
            except ImportError:
                logger.warning("pydub未安装，跳过音频格式转换")
            except Exception as e:
                logger.warning(f"音频格式转换失败: {str(e)}，使用原文件")
            
            # 获取Token
            token = get_aliyun_token()
            
            # 识别音频
            result = recognize_audio_file(audio_file_path, token)
            
            recognized_text = result["text"]
            confidence = result.get("confidence", 0.0)
            
            # 验证识别结果（如果提供了期望文本）
            validation_passed = True
            if expected_text:
                # 简单的文本匹配（去除空格和标点后比较）
                import re
                normalized_recognized = re.sub(r'[\s\.,，。！？]', '', recognized_text)
                normalized_expected = re.sub(r'[\s\.,，。！？]', '', expected_text)
                validation_passed = normalized_recognized == normalized_expected
            
            return ASRResponse(
                recognizedText=recognized_text,
                confidence=confidence,
                validationPassed=validation_passed,
                message="识别成功" if validation_passed else "识别结果与期望文本不一致"
            )
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            if os.path.exists(audio_file_path) and audio_file_path != temp_file.name:
                os.unlink(audio_file_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ASR识别失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


@router.post("/recognize-by-file-id", response_model=ASRResponse)
async def recognize_by_file_id(
    request: ASRRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    通过文件ID识别音频（文件已上传到服务器）
    
    Args:
        request: ASR请求，包含fileId和可选的expectedText
        current_user: 当前用户
        
    Returns:
        ASRResponse: 识别结果
    """
    try:
        from scripts.file_dao import FileDAO
        
        # 获取文件信息
        file_dao = FileDAO()
        file_info = file_dao.get_file_by_id(request.fileId)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 检查文件是否属于当前用户
        if file_info.get("user_id") != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="无权访问此文件")
        
        # 获取文件路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        outputs_dir = os.path.join(project_root, "outputs")
        file_path = os.path.join(outputs_dir, file_info["name"])
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 获取Token
        token = get_aliyun_token()
        
        # 识别音频
        result = recognize_audio_file(file_path, token)
        
        recognized_text = result["text"]
        confidence = result.get("confidence", 0.0)
        
        # 验证识别结果
        validation_passed = True
        if request.expectedText:
            import re
            normalized_recognized = re.sub(r'[\s\.,，。！？]', '', recognized_text)
            normalized_expected = re.sub(r'[\s\.,，。！？]', '', request.expectedText)
            validation_passed = normalized_recognized == normalized_expected
        
        return ASRResponse(
            recognizedText=recognized_text,
            confidence=confidence,
            validationPassed=validation_passed,
            message="识别成功" if validation_passed else "识别结果与期望文本不一致"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ASR识别失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


@router.get("/health")
async def asr_health():
    """检查ASR服务健康状态"""
    config_ok = bool(ALIYUN_ACCESS_KEY_ID and ALIYUN_ACCESS_KEY_SECRET and ALIYUN_ASR_APP_KEY)
    
    return {
        "status": "ok" if config_ok else "not_configured",
        "configured": config_ok,
        "message": "ASR服务已配置" if config_ok else "ASR服务未配置，请设置环境变量"
    }

