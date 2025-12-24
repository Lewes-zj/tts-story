"""
ASR语音识别校验API
使用FunASR SenseVoiceSmall模型进行语音转文字，并校验识别结果与标准文本的相似度
"""

import os
import sys
import logging
import tempfile
from typing import Optional
from difflib import SequenceMatcher

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/asr", tags=["语音识别校验"])

# 全局模型变量，在服务启动时加载一次
_asr_model = None

# 标准录音文本（与前端保持一致）
STANDARD_TEXT = "床前明月光，疑是地上霜。举头望明月，低头思故乡。这首古诗陪伴我们成长，承载着无数人的美好回忆。"


def load_funasr_model():
    """
    全局加载FunASR SenseVoiceSmall模型
    此函数在服务启动时调用一次，避免每次请求都重新加载模型
    """
    global _asr_model
    
    if _asr_model is not None:
        logger.info("FunASR模型已加载，跳过重复加载")
        return _asr_model
    
    try:
        logger.info("开始加载FunASR SenseVoiceSmall模型...")
        
        # 导入funasr库
        from funasr import AutoModel
        
        # 加载SenseVoiceSmall模型
        # model_dir: 模型路径，如果为None则自动下载
        # device: 设备类型，'cpu'或'cuda'
        # disable_log: 是否禁用日志
        
        # 尝试使用GPU，如果不可用则使用CPU
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"使用设备: {device}")
        
        # 加载模型
        # iic/SenseVoiceSmall 是FunASR提供的轻量级中文语音识别模型
        # language: 指定语言为中文
        # use_itn: 启用逆文本标准化，将数字、日期等转换为标准文本格式
        _asr_model = AutoModel(
            model="iic/SenseVoiceSmall",
            device=device,
            disable_log=False
        )
        
        logger.info("FunASR SenseVoiceSmall模型加载成功")
        return _asr_model
        
    except ImportError as e:
        error_msg = str(e)
        logger.error(f"无法导入funasr库或其依赖: {error_msg}")
        
        # 提供更详细的错误信息
        if "torchaudio" in error_msg:
            logger.error("缺少torchaudio依赖，请安装: pip install torchaudio")
            detail_msg = "FunASR需要torchaudio依赖，请安装: pip install torchaudio"
        elif "torch" in error_msg:
            logger.error("缺少torch依赖，请安装: pip install torch")
            detail_msg = "FunASR需要torch依赖，请安装: pip install torch"
        else:
            logger.error("请安装funasr及其依赖: pip install funasr torch torchaudio")
            detail_msg = f"FunASR库或其依赖未安装: {error_msg}，请安装: pip install funasr torch torchaudio"
        
        raise HTTPException(
            status_code=500,
            detail=detail_msg
        )
    except Exception as e:
        logger.error(f"加载FunASR模型失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"模型加载失败: {str(e)}"
        )


def clean_funasr_text(text: str) -> str:
    """
    清理FunASR识别结果中的特殊标记
    
    FunASR可能会在识别结果中添加特殊标记，如：
    <|zh|><|NEUTRAL|><|Speech|><|withitn|>文本内容
    
    这个函数会去除这些标记，只保留实际的文本内容
    
    Args:
        text: 原始识别文本
        
    Returns:
        清理后的文本
    """
    import re
    
    if not text:
        return ""
    
    # 去除FunASR的特殊标记，格式如：<|标记名|>
    # 例如：<|zh|>, <|NEUTRAL|>, <|Speech|>, <|withitn|> 等
    # 使用非贪婪匹配，确保正确匹配所有标记
    text = re.sub(r'<\|[^|]+\|>', '', text)
    
    # 去除标记后可能留下的多余空格（但保留文本中的正常空格）
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的相似度
    
    使用SequenceMatcher算法计算相似度，范围0-1
    也可以使用Levenshtein距离，但SequenceMatcher对中文效果更好
    
    Args:
        text1: 第一个文本（通常是识别文本）
        text2: 第二个文本（通常是标准文本）
        
    Returns:
        相似度值，范围0-1，1表示完全相同
    """
    import re
    
    # 先清理FunASR的特殊标记
    text1 = clean_funasr_text(text1)
    
    # 去除所有空白字符和常见标点符号，只比较核心内容
    normalize = lambda s: re.sub(r'[\s\.,，。！？；：、""''（）()【】\[\]《》]', '', s)
    
    normalized_text1 = normalize(text1)
    normalized_text2 = normalize(text2)
    
    # 如果归一化后都为空，返回1.0（认为相同）
    if not normalized_text1 and not normalized_text2:
        return 1.0
    if not normalized_text1 or not normalized_text2:
        return 0.0
    
    # 使用SequenceMatcher计算相似度
    similarity = SequenceMatcher(None, normalized_text1, normalized_text2).ratio()
    
    return similarity


def recognize_audio_with_funasr(audio_file_path: str) -> str:
    """
    使用FunASR识别音频文件
    
    Args:
        audio_file_path: 音频文件路径
        
    Returns:
        识别出的文本内容
    """
    global _asr_model
    
    if _asr_model is None:
        raise HTTPException(
            status_code=500,
            detail="ASR模型未加载，请重启服务"
        )
    
    try:
        # 使用FunASR进行语音识别
        # res: 识别结果列表，每个元素是一个字典，包含text和timestamp等信息
        # language: 指定语言为中文
        # use_itn: 启用逆文本标准化，将数字、日期等转换为标准文本格式
        res = _asr_model.generate(
            input=audio_file_path,
            language="zh",  # 指定中文
            use_itn=True   # 启用逆文本标准化
        )
        
        # 解析识别结果
        # res的结构可能是: [{"text": "识别出的文本", ...}, ...]
        if isinstance(res, list) and len(res) > 0:
            # 如果返回的是列表，取第一个结果
            if isinstance(res[0], dict):
                recognized_text = res[0].get("text", "")
            else:
                recognized_text = str(res[0])
        elif isinstance(res, dict):
            recognized_text = res.get("text", "")
        else:
            recognized_text = str(res)
        
        # 如果识别结果为空，返回提示
        if not recognized_text or not recognized_text.strip():
            logger.warning(f"音频识别结果为空: {audio_file_path}")
            recognized_text = ""
        else:
            # 清理FunASR的特殊标记
            recognized_text = clean_funasr_text(recognized_text)
        
        logger.info(f"识别结果（清理后）: {recognized_text}")
        return recognized_text.strip()
        
    except Exception as e:
        logger.error(f"FunASR识别失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"语音识别失败: {str(e)}"
        )


class ASRVerifyResponse(BaseModel):
    """ASR校验响应模型"""
    success: bool
    data: dict


@router.post("/verify", response_model=ASRVerifyResponse)
async def verify_audio(
    file: UploadFile = File(...),
    text: Optional[str] = Form(None)
):
    """
    校验录音内容是否正确
    
    接收音频文件，使用FunASR进行语音识别，然后与标准文本进行相似度比对。
    只有当相似度 > 90% 时，才判定为校验通过。
    
    Args:
        file: 音频文件（支持 webm, wav, mp3 等格式）
        text: 标准文本（可选，如果不提供则使用后端配置的标准文本）
        
    Returns:
        ASRVerifyResponse: 包含识别文本、相似度和校验结果的响应
    """
    # 确保模型已加载
    if _asr_model is None:
        try:
            load_funasr_model()
        except Exception as e:
            logger.error(f"模型加载失败: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="ASR模型加载失败，请检查服务配置"
            )
    
    # 使用提供的标准文本，或使用后端配置的默认文本
    standard_text = text if text else STANDARD_TEXT
    
    temp_file_path = None
    temp_wav_path = None
    
    try:
        # 读取上传的音频文件
        content = await file.read()
        if not content or len(content) == 0:
            raise HTTPException(status_code=400, detail="上传的音频文件为空")
        
        # 保存为临时文件
        file_extension = os.path.splitext(file.filename or "audio")[1].lower()
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_extension,
            prefix=f"asr_verify_{os.getpid()}_"
        )
        temp_file_path = temp_file.name
        temp_file.write(content)
        temp_file.close()
        
        logger.info(f"保存临时音频文件: {temp_file_path}, 格式: {file_extension}")
        
        # 如果音频格式不是wav，尝试转换为wav（FunASR对wav格式支持最好）
        audio_file_path = temp_file_path
        if file_extension not in ['.wav', '.WAV']:
            try:
                from pydub import AudioSegment
                
                logger.info(f"转换音频格式: {file_extension} -> wav")
                audio = AudioSegment.from_file(temp_file_path)
                
                # 转换为wav格式，采样率16kHz（FunASR推荐）
                temp_wav = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix='.wav',
                    prefix=f"asr_verify_wav_{os.getpid()}_"
                )
                temp_wav_path = temp_wav.name
                temp_wav.close()
                
                # 导出为wav格式，16kHz采样率，单声道
                audio = audio.set_frame_rate(16000).set_channels(1)
                audio.export(temp_wav_path, format="wav")
                
                audio_file_path = temp_wav_path
                logger.info(f"音频格式转换完成: {temp_wav_path}")
                
            except ImportError:
                logger.warning("pydub未安装，跳过音频格式转换，直接使用原文件")
            except Exception as e:
                logger.warning(f"音频格式转换失败: {str(e)}，使用原文件")
                audio_file_path = temp_file_path
        
        # 使用FunASR进行语音识别
        recognized_text = recognize_audio_with_funasr(audio_file_path)
        
        # 计算相似度（recognize_audio_with_funasr已经清理了标记，calculate_similarity会再次清理确保）
        similarity = calculate_similarity(recognized_text, standard_text)
        
        # 判定标准：相似度 > 90% 才通过
        similarity_threshold = 0.90
        passed = similarity > similarity_threshold
        
        # 记录清理后的文本用于调试
        cleaned_recognized = clean_funasr_text(recognized_text)
        logger.info(f"识别文本（原始）: {recognized_text}")
        logger.info(f"识别文本（清理后）: {cleaned_recognized}")
        logger.info(f"标准文本: {standard_text}")
        logger.info(f"相似度: {similarity:.2%}, 阈值: {similarity_threshold:.2%}, 结果: {'通过' if passed else '不通过'}")
        
        return ASRVerifyResponse(
            success=True,
            data={
                "text": recognized_text,
                "similarity": round(similarity, 4),  # 保留4位小数
                "passed": passed
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ASR校验失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"校验失败: {str(e)}"
        )
    finally:
        # 清理临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"删除临时文件失败: {temp_file_path}, {str(e)}")
        
        if temp_wav_path and os.path.exists(temp_wav_path):
            try:
                os.unlink(temp_wav_path)
            except Exception as e:
                logger.warning(f"删除临时WAV文件失败: {temp_wav_path}, {str(e)}")


@router.get("/verify/health")
async def verify_health():
    """检查ASR校验服务健康状态"""
    global _asr_model
    
    model_loaded = _asr_model is not None
    
    return {
        "status": "ok" if model_loaded else "not_loaded",
        "model_loaded": model_loaded,
        "message": "ASR校验服务已就绪" if model_loaded else "ASR模型未加载，请等待服务启动完成"
    }


# 在模块导入时尝试加载模型（可选，也可以在服务启动时手动调用）
# 注意：如果模型很大，启动时加载可能会比较慢
def initialize_model():
    """初始化模型（在服务启动时调用）"""
    try:
        load_funasr_model()
        logger.info("ASR校验服务初始化完成")
    except Exception as e:
        logger.error(f"ASR校验服务初始化失败: {str(e)}")
        # 不抛出异常，允许服务启动，但API调用时会失败

