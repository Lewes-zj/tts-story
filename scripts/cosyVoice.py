"""
CosyVoice 声音复刻 API 集成模块

基于阿里云 DashScope SDK 实现声音复刻和语音合成功能。
支持创建、查询、更新、删除音色，以及使用复刻音色进行语音合成。

参考文档: https://help.aliyun.com/zh/model-studio/cosyvoice-clone-api
"""

import os
import time
import logging
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum

try:
    import dashscope
    from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer, AudioFormat
    from dashscope.common.error import AuthenticationError, ServiceUnavailableError, DashScopeException
except ImportError:
    raise ImportError(
        "DashScope SDK 未安装。请运行: pip install dashscope"
    )

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TargetModel(str, Enum):
    """支持的语音合成模型枚举"""
    COSYVOICE_V1 = "cosyvoice-v1"
    COSYVOICE_V2 = "cosyvoice-v2"
    COSYVOICE_V3_FLASH = "cosyvoice-v3-flash"
    COSYVOICE_V3_PLUS = "cosyvoice-v3-plus"


@dataclass
class VoiceInfo:
    """音色信息数据类"""
    voice_id: str
    prefix: str
    target_model: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    description: Optional[str] = None


@dataclass
class VoiceEnrollmentRequest:
    """创建音色请求参数"""
    target_model: str
    prefix: str
    audio_url: Optional[str] = None
    audio_file: Optional[str] = None
    description: Optional[str] = None


@dataclass
class VoiceUpdateRequest:
    """更新音色请求参数"""
    voice_id: str
    description: Optional[str] = None
    audio_url: Optional[str] = None
    audio_file: Optional[str] = None


@dataclass
class SpeechSynthesisRequest:
    """语音合成请求参数"""
    text: str
    voice_id: Optional[str] = None
    model: Optional[str] = None
    speech_rate: Optional[float] = None
    volume: Optional[float] = None
    pitch: Optional[float] = None
    format: str = "wav"
    sample_rate: int = 24000


@dataclass
class SpeechSynthesisResponse:
    """语音合成响应数据"""
    audio_data: bytes
    format: str
    sample_rate: int
    request_id: Optional[str] = None


class CosyVoiceService:
    """CosyVoice 声音复刻服务类
    
    提供完整的音色管理和语音合成功能。
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 CosyVoice 服务

        Args:
            api_key: DashScope API Key。如果为 None，将从环境变量 DASHSCOPE_API_KEY 读取

        Raises:
            ValueError: 如果 API Key 未配置
        """
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API Key 未配置。请设置环境变量 DASHSCOPE_API_KEY 或传入 api_key 参数"
            )
        
        dashscope.api_key = self.api_key
        self.enrollment_service = VoiceEnrollmentService()
        # SpeechSynthesizer 需要在调用时动态创建，因为需要 model 和 voice 参数
        # self.synthesizer 将在 synthesize_speech 方法中动态创建
        logger.info("CosyVoice 服务初始化成功")

    # ==================== 音色管理功能 ====================

    def create_voice(
        self,
        target_model: str,
        prefix: str,
        audio_url: Optional[str] = None,
        audio_file: Optional[str] = None,
        description: Optional[str] = None,
        wait_for_completion: bool = True,
        timeout: int = 300
    ) -> VoiceInfo:
        """
        创建音色（声音复刻）

        Args:
            target_model: 驱动音色的语音合成模型
                - cosyvoice-v1: 兼容旧版
                - cosyvoice-v2: 兼容旧版
                - cosyvoice-v3-flash: 平衡效果与成本
                - cosyvoice-v3-plus: 最佳音质（推荐）
            prefix: 音色前缀（仅允许数字和小写字母，小于十个字符）
            audio_url: 公网可访问的音频 URL（WAV/MP3/M4A，10-20秒，≤10MB）
            audio_file: 本地音频文件路径（将自动上传到公网）
            description: 音色描述信息（注意：API 不支持此参数，仅用于内部记录）
            wait_for_completion: 是否等待创建完成
            timeout: 等待超时时间（秒）

        Returns:
            VoiceInfo: 创建的音色信息

        Raises:
            ValueError: 参数验证失败
            AuthenticationError: API Key 认证失败
            DashScopeException: DashScope API 错误（包括输入参数无效）
            ServiceUnavailableError: 服务不可用
            TimeoutError: 等待超时
        """
        # 参数验证
        if not audio_url and not audio_file:
            raise ValueError("必须提供 audio_url 或 audio_file 之一")
        
        if audio_url and audio_file:
            raise ValueError("不能同时提供 audio_url 和 audio_file")
        
        if len(prefix) >= 10:
            raise ValueError("prefix 必须小于十个字符")
        
        if not prefix.replace('_', '').replace('-', '').isalnum() or not prefix.islower():
            raise ValueError("prefix 仅允许数字和小写字母")

        # 如果提供了本地文件，需要先上传到公网（这里假设调用者已处理）
        # 实际使用时，可能需要先上传到 OSS 等对象存储服务
        if audio_file:
            logger.warning("audio_file 参数需要先上传到公网可访问的位置，请使用 audio_url")
            raise ValueError("请先上传音频文件到公网可访问的位置，然后使用 audio_url")

        logger.info(f"开始创建音色: prefix={prefix}, target_model={target_model}")
        
        try:
            # 创建音色（异步任务）
            # 注意：create_voice 不支持 description 参数，只支持 target_model, prefix, url, language_hints
            # 注意：create_voice 可能会因为 API 响应超时而失败，建议使用 wait_for_completion=False
            try:
                voice_id = self.enrollment_service.create_voice(
                    target_model=target_model,
                    prefix=prefix,
                    url=audio_url
                )
                logger.info(f"音色创建请求已提交: voice_id={voice_id}")
            except Exception as api_error:
                # 如果 API 调用超时，但可能已经创建成功，尝试通过查询来获取 voice_id
                error_str = str(api_error).lower()
                if "timeout" in error_str or "responsetimeout" in error_str:
                    logger.warning(f"API 调用超时，但任务可能已提交。尝试通过 prefix 查询音色...")
                    # 等待几秒后尝试查询
                    time.sleep(3)
                    # 尝试通过 prefix 和 target_model 查询音色
                    voices = self.list_voices(target_model=target_model, prefix=prefix)
                    if voices:
                        # 找到最新的音色（可能是刚创建的）
                        latest_voice = max(voices, key=lambda v: v.created_at or "")
                        if latest_voice.status in ["creating", "ready"]:
                            voice_id = latest_voice.voice_id
                            logger.info(f"通过查询找到音色: voice_id={voice_id}, status={latest_voice.status}")
                        else:
                            raise RuntimeError(f"找到音色但状态异常: {latest_voice.status}")
                    else:
                        # 如果查询不到，可能是真的失败了
                        logger.error("API 超时且无法通过查询找到音色，请稍后重试或使用 wait_for_completion=False")
                        raise RuntimeError(f"创建音色超时，且无法确认是否已创建。请稍后使用 list_voices() 查询，或使用 wait_for_completion=False 参数")
                else:
                    # 其他错误直接抛出
                    raise

            # 如果不需要等待完成，直接返回
            if not wait_for_completion:
                return VoiceInfo(
                    voice_id=voice_id,
                    prefix=prefix,
                    target_model=target_model,
                    status="creating",
                    description=description
                )

            # 等待创建完成
            start_time = time.time()
            while time.time() - start_time < timeout:
                voice_info = self.get_voice(voice_id)
                
                if voice_info.status == "ready":
                    logger.info(f"音色创建完成: voice_id={voice_id}")
                    return voice_info
                elif voice_info.status == "failed":
                    raise RuntimeError(f"音色创建失败: voice_id={voice_id}")
                
                time.sleep(2)  # 每2秒查询一次状态
            
            raise TimeoutError(f"音色创建超时: voice_id={voice_id}, timeout={timeout}秒")

        except AuthenticationError as e:
            logger.error(f"API Key 认证失败: {e}")
            raise
        except DashScopeException as e:
            logger.error(f"DashScope API 错误: {e}")
            raise
        except ServiceUnavailableError as e:
            logger.error(f"服务不可用: {e}")
            raise
        except Exception as e:
            logger.error(f"创建音色时发生错误: {e}")
            raise

    def list_voices(
        self,
        target_model: Optional[str] = None,
        prefix: Optional[str] = None
    ) -> List[VoiceInfo]:
        """
        查询音色列表

        Args:
            target_model: 按语音合成模型筛选（可选）
            prefix: 按前缀筛选（可选）

        Returns:
            List[VoiceInfo]: 音色信息列表

        Raises:
            AuthenticationError: API Key 认证失败
            ServiceUnavailableError: 服务不可用
        """
        logger.info(f"查询音色列表: target_model={target_model}, prefix={prefix}")
        
        try:
            voices = self.enrollment_service.list_voices(
                target_model=target_model,
                prefix=prefix
            )
            
            result = []
            for voice in voices:
                result.append(VoiceInfo(
                    voice_id=voice.get("voice_id", ""),
                    prefix=voice.get("prefix", ""),
                    target_model=voice.get("target_model", ""),
                    status=voice.get("status", "unknown"),
                    created_at=voice.get("created_at"),
                    updated_at=voice.get("updated_at"),
                    description=voice.get("description")
                ))
            
            logger.info(f"查询到 {len(result)} 个音色")
            return result

        except AuthenticationError as e:
            logger.error(f"API Key 认证失败: {e}")
            raise
        except ServiceUnavailableError as e:
            logger.error(f"服务不可用: {e}")
            raise
        except Exception as e:
            logger.error(f"查询音色列表时发生错误: {e}")
            raise

    def get_voice(self, voice_id: str) -> VoiceInfo:
        """
        查询音色详情

        Args:
            voice_id: 音色 ID

        Returns:
            VoiceInfo: 音色详细信息

        Raises:
            ValueError: 音色 ID 无效
            AuthenticationError: API Key 认证失败
            ServiceUnavailableError: 服务不可用
        """
        if not voice_id:
            raise ValueError("voice_id 不能为空")

        logger.info(f"查询音色详情: voice_id={voice_id}")
        
        try:
            voice = self.enrollment_service.get_voice(voice_id)
            
            return VoiceInfo(
                voice_id=voice.get("voice_id", voice_id),
                prefix=voice.get("prefix", ""),
                target_model=voice.get("target_model", ""),
                status=voice.get("status", "unknown"),
                created_at=voice.get("created_at"),
                updated_at=voice.get("updated_at"),
                description=voice.get("description")
            )

        except AuthenticationError as e:
            logger.error(f"API Key 认证失败: {e}")
            raise
        except ServiceUnavailableError as e:
            logger.error(f"服务不可用: {e}")
            raise
        except Exception as e:
            logger.error(f"查询音色详情时发生错误: {e}")
            raise

    def update_voice(
        self,
        voice_id: str,
        description: Optional[str] = None,
        audio_url: Optional[str] = None,
        audio_file: Optional[str] = None
    ) -> VoiceInfo:
        """
        更新音色信息

        Args:
            voice_id: 音色 ID
            description: 新的描述信息（注意：API 不支持此参数，仅用于内部记录）
            audio_url: 新的音频 URL（用于重新训练）
            audio_file: 新的本地音频文件路径

        Returns:
            VoiceInfo: 更新后的音色信息

        Raises:
            ValueError: 参数验证失败
            AuthenticationError: API Key 认证失败
            DashScopeException: DashScope API 错误（包括输入参数无效）
            ServiceUnavailableError: 服务不可用
        """
        if not voice_id:
            raise ValueError("voice_id 不能为空")

        if audio_file:
            logger.warning("audio_file 参数需要先上传到公网可访问的位置，请使用 audio_url")
            raise ValueError("请先上传音频文件到公网可访问的位置，然后使用 audio_url")

        logger.info(f"更新音色: voice_id={voice_id}")
        
        try:
            # 注意：update_voice 只支持 voice_id 和 url 参数，不支持 description
            if audio_url:
                self.enrollment_service.update_voice(
                    voice_id=voice_id,
                    url=audio_url
                )
            else:
                # 如果没有提供 audio_url，说明只是想更新描述，但 API 不支持
                logger.warning("update_voice API 不支持更新 description，只支持更新音频 URL")
                if description:
                    logger.info(f"description 参数被忽略: {description}")
            
            logger.info(f"音色更新成功: voice_id={voice_id}")
            return self.get_voice(voice_id)

        except AuthenticationError as e:
            logger.error(f"API Key 认证失败: {e}")
            raise
        except DashScopeException as e:
            logger.error(f"DashScope API 错误: {e}")
            raise
        except ServiceUnavailableError as e:
            logger.error(f"服务不可用: {e}")
            raise
        except Exception as e:
            logger.error(f"更新音色时发生错误: {e}")
            raise

    def delete_voice(self, voice_id: str) -> bool:
        """
        删除音色

        Args:
            voice_id: 音色 ID

        Returns:
            bool: 删除是否成功

        Raises:
            ValueError: 音色 ID 无效
            AuthenticationError: API Key 认证失败
            ServiceUnavailableError: 服务不可用
        """
        if not voice_id:
            raise ValueError("voice_id 不能为空")

        logger.info(f"删除音色: voice_id={voice_id}")
        
        try:
            self.enrollment_service.delete_voice(voice_id)
            logger.info(f"音色删除成功: voice_id={voice_id}")
            return True

        except AuthenticationError as e:
            logger.error(f"API Key 认证失败: {e}")
            raise
        except ServiceUnavailableError as e:
            logger.error(f"服务不可用: {e}")
            raise
        except Exception as e:
            logger.error(f"删除音色时发生错误: {e}")
            raise

    # ==================== 语音合成功能 ====================

    def synthesize_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model: Optional[str] = None,
        speech_rate: Optional[float] = None,
        volume: Optional[float] = None,
        pitch: Optional[float] = None,
        format: str = "wav",
        sample_rate: int = 24000
    ) -> SpeechSynthesisResponse:
        """
        使用复刻音色进行语音合成

        重要：指定的语音合成模型必须与创建音色时的 target_model 一致。

        Args:
            text: 要合成的文本内容
            voice_id: 复刻音色的 ID（如果使用复刻音色）
            model: 语音合成模型（必须与创建音色时的 target_model 一致）
            speech_rate: 语速（可选，范围通常为 0.5-2.0）
            volume: 音量（可选，范围通常为 0.0-1.0）
            pitch: 音调（可选）
            format: 输出音频格式（wav/mp3/m4a，默认 wav）
            sample_rate: 采样率（默认 24000）

        Returns:
            SpeechSynthesisResponse: 合成结果

        Raises:
            ValueError: 参数验证失败
            AuthenticationError: API Key 认证失败
            DashScopeException: DashScope API 错误（包括输入参数无效）
            ServiceUnavailableError: 服务不可用
        """
        if not text:
            raise ValueError("text 不能为空")

        if voice_id and not model:
            # 如果提供了 voice_id，需要先查询音色信息获取 target_model
            voice_info = self.get_voice(voice_id)
            model = voice_info.target_model
            logger.info(f"从音色信息获取模型: model={model}")

        if not model:
            raise ValueError("必须指定 model 参数，或提供 voice_id 以自动获取")

        logger.info(f"开始语音合成: text_length={len(text)}, voice_id={voice_id}, model={model}")
        
        try:
            # SpeechSynthesizer 需要在初始化时传入 model 和 voice
            # 如果没有 voice_id，必须提供默认音色（使用复刻音色时 voice_id 是必需的）
            if not voice_id:
                raise ValueError("使用复刻音色进行语音合成时，必须提供 voice_id 参数")
            
            # 将字符串格式转换为 AudioFormat 枚举
            audio_format = AudioFormat.DEFAULT
            if format.lower() == "wav":
                if sample_rate == 24000:
                    audio_format = AudioFormat.WAV_24000HZ_MONO_16BIT
                elif sample_rate == 16000:
                    audio_format = AudioFormat.WAV_16000HZ_MONO_16BIT
                elif sample_rate == 22050:
                    audio_format = AudioFormat.WAV_22050HZ_MONO_16BIT
                elif sample_rate == 44100:
                    audio_format = AudioFormat.WAV_44100HZ_MONO_16BIT
                elif sample_rate == 48000:
                    audio_format = AudioFormat.WAV_48000HZ_MONO_16BIT
                else:
                    audio_format = AudioFormat.WAV_24000HZ_MONO_16BIT  # 默认
            elif format.lower() == "mp3":
                if sample_rate == 24000:
                    audio_format = AudioFormat.MP3_24000HZ_MONO_256KBPS
                else:
                    audio_format = AudioFormat.MP3_24000HZ_MONO_256KBPS  # 默认
            
            # 转换 volume 范围：从 0.0-1.0 转换为 0-100
            volume_int = 50  # 默认值
            if volume is not None:
                if volume <= 1.0:
                    # 假设是 0.0-1.0 范围，转换为 0-100
                    volume_int = int(volume * 100)
                else:
                    # 已经是 0-100 范围
                    volume_int = int(volume)
                volume_int = max(0, min(100, volume_int))  # 限制在 0-100 范围内
            
            # 创建 SpeechSynthesizer 实例（需要 model 和 voice）
            synthesizer = SpeechSynthesizer(
                model=model,
                voice=voice_id,  # 使用复刻音色的 voice_id
                format=audio_format,
                volume=volume_int,
                speech_rate=speech_rate if speech_rate is not None else 1.0,
                pitch_rate=pitch if pitch is not None else 1.0
            )
            
            # 调用语音合成接口
            result = synthesizer.call(text=text)
            
            if result.status_code == 200:
                audio_data = result.get_audio_data()
                request_id = result.request_id
                
                logger.info(f"语音合成成功: request_id={request_id}, audio_size={len(audio_data)} bytes")
                
                return SpeechSynthesisResponse(
                    audio_data=audio_data,
                    format=format,
                    sample_rate=sample_rate,
                    request_id=request_id
                )
            else:
                error_msg = f"语音合成失败: status_code={result.status_code}, message={result.message}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

        except AuthenticationError as e:
            logger.error(f"API Key 认证失败: {e}")
            raise
        except DashScopeException as e:
            logger.error(f"DashScope API 错误: {e}")
            raise
        except ServiceUnavailableError as e:
            logger.error(f"服务不可用: {e}")
            raise
        except Exception as e:
            logger.error(f"语音合成时发生错误: {e}")
            raise

    def synthesize_speech_to_file(
        self,
        text: str,
        output_path: str,
        voice_id: Optional[str] = None,
        model: Optional[str] = None,
        speech_rate: Optional[float] = None,
        volume: Optional[float] = None,
        pitch: Optional[float] = None,
        format: str = "wav",
        sample_rate: int = 24000
    ) -> str:
        """
        使用复刻音色进行语音合成并保存到文件

        Args:
            text: 要合成的文本内容
            output_path: 输出文件路径
            voice_id: 复刻音色的 ID
            model: 语音合成模型
            speech_rate: 语速
            volume: 音量
            pitch: 音调
            format: 输出音频格式
            sample_rate: 采样率

        Returns:
            str: 输出文件路径

        Raises:
            IOError: 文件写入失败
        """
        response = self.synthesize_speech(
            text=text,
            voice_id=voice_id,
            model=model,
            speech_rate=speech_rate,
            volume=volume,
            pitch=pitch,
            format=format,
            sample_rate=sample_rate
        )
        
        try:
            with open(output_path, "wb") as f:
                f.write(response.audio_data)
            logger.info(f"音频已保存到: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"保存音频文件失败: {e}")
            raise IOError(f"无法写入文件 {output_path}: {e}")


# ==================== 使用示例 ====================

def example_usage():
    """使用示例"""
    # 1. 初始化服务（从环境变量读取 API Key）
    service = CosyVoiceService()
    
    # 或者直接传入 API Key
    # service = CosyVoiceService(api_key="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    
    # 2. 创建音色
    audio_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/cosyvoice/cosyvoice-zeroshot-sample.wav"
    voice_info = service.create_voice(
        target_model=TargetModel.COSYVOICE_V3_PLUS.value,
        prefix="myvoice",
        audio_url=audio_url,
        description="我的自定义音色"
    )
    print(f"音色创建成功: {voice_info.voice_id}")
    
    # 3. 查询音色列表
    voices = service.list_voices(target_model=TargetModel.COSYVOICE_V3_PLUS.value)
    print(f"共有 {len(voices)} 个音色")
    
    # 4. 查询音色详情
    voice_detail = service.get_voice(voice_info.voice_id)
    print(f"音色状态: {voice_detail.status}")
    
    # 5. 使用音色进行语音合成
    service.synthesize_speech(
        text="你好，这是使用复刻音色合成的语音。",
        voice_id=voice_info.voice_id,
        speech_rate=1.0,
        volume=1.0
    )
    
    # 6. 保存音频到文件
    service.synthesize_speech_to_file(
        text="你好，这是使用复刻音色合成的语音。",
        output_path="output.wav",
        voice_id=voice_info.voice_id
    )
    
    # 7. 更新音色描述
    service.update_voice(
        voice_id=voice_info.voice_id,
        description="更新后的描述"
    )
    
    # 8. 删除音色（可选）
    # service.delete_voice(voice_info.voice_id)


if __name__ == "__main__":
    example_usage()

