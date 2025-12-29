#!/usr/bin/env python3.10
"""
CosyVoice V3 语音合成脚本
使用 Python 3.10 运行
"""

import os
import time
import argparse
from typing import Optional
import yaml
import dashscope
from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer, SpeechSynthesizerObjectPool


def _load_config_model() -> Optional[str]:
    """
    从配置文件中加载 cosyvoice_model
    
    Returns:
        模型名称，如果配置文件不存在或配置项不存在则返回 None
    """
    try:
        # 获取项目根目录
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(current_file))
        config_path = os.path.join(project_root, "config", "config.yaml")
        
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                if config and "character_audio_clone" in config:
                    model = config["character_audio_clone"].get("cosyvoice_model")
                    if model:
                        return model
    except Exception:
        # 如果读取配置文件失败，返回 None，使用默认值
        pass
    return None


class CosyVoiceV3:
    """CosyVoice V3 语音克隆和合成类"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        target_model: Optional[str] = None,
        voice_prefix: str = "minivoice",
        max_attempts: int = 30,
        poll_interval: int = 10,
        pool_size: int = 20,
        use_object_pool: bool = True
    ):
        """
        初始化 CosyVoice V3 客户端
        
        Args:
            api_key: DashScope API Key，如果不提供则从环境变量 DASHSCOPE_API_KEY 读取
            target_model: 目标模型名称，如果不提供则从配置文件读取，配置文件不存在则使用默认值 "cosyvoice-v3-plus"
            voice_prefix: 音色前缀，仅允许数字和小写字母，小于十个字符，默认为 "minivoice"
            max_attempts: 轮询最大尝试次数，默认为 30
            poll_interval: 轮询间隔（秒），默认为 10
            pool_size: 对象池大小，默认为 20（建议设置为峰值并发数的 1.5 至 2 倍）
            use_object_pool: 是否使用对象池，默认为 True（高并发场景推荐使用）
        """
        # 设置 API Key
        if api_key:
            dashscope.api_key = api_key
        else:
            dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
        
        if not dashscope.api_key:
            raise ValueError("API key is required. Set DASHSCOPE_API_KEY environment variable or pass api_key parameter.")
        
        # 从配置文件读取模型名称，如果未提供 target_model 参数
        if target_model is None:
            config_model = _load_config_model()
            self.target_model = config_model if config_model else "cosyvoice-v3-plus"
        else:
            self.target_model = target_model
        self.voice_prefix = voice_prefix
        self.max_attempts = max_attempts
        self.poll_interval = poll_interval
        self.service = VoiceEnrollmentService()
        self.use_object_pool = use_object_pool
        self.pool_size = pool_size
        
        # 延迟初始化对象池（不在 __init__ 中立即创建连接）
        # 对象池将在第一次使用时才初始化，避免初始化时连接失败
        self.object_pool = None
        self._object_pool_initialized = False
        self._object_pool_init_failed = False
    
    def synthesize(
        self,
        audio_url: str,
        text_to_synthesize: str,
        output_file: Optional[str] = None
    ) -> bytes:
        """
        使用音频 URL 创建音色并合成语音
        
        Args:
            audio_url: 公网可访问的音频 URL，用于音色克隆
            text_to_synthesize: 要合成的文本内容
            output_file: 输出文件路径（可选），如果不提供则只返回音频数据
        
        Returns:
            二进制音频数据
            
        Raises:
            RuntimeError: 当音色创建失败或轮询超时时
            Exception: 当语音合成失败时
        """
        # 1. 创建音色
        voice_id = self._create_voice(audio_url)
        
        # 2. 轮询音色状态
        self._poll_voice_status(voice_id)
        
        # 3. 语音合成
        audio_data = self._synthesize_speech(voice_id, text_to_synthesize)
        
        # 4. 保存文件（如果提供了输出路径）
        if output_file:
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"Audio saved to {output_file}")
        
        return audio_data
    
    def _create_voice(self, audio_url: str) -> str:
        """
        创建音色（私有方法）
        
        Args:
            audio_url: 公网可访问的音频 URL
        
        Returns:
            生成的音色 ID
        """
        print("--- Step 1: Creating voice enrollment ---")
        try:
            voice_id = self.service.create_voice(
                target_model=self.target_model,
                prefix=self.voice_prefix,
                url=audio_url
            )
            print(f"Voice enrollment submitted successfully. Request ID: {self.service.get_last_request_id()}")
            print(f"Generated Voice ID: {voice_id}")
            return voice_id
        except Exception as e:
            print(f"Error during voice creation: {e}")
            raise e
    
    def _poll_voice_status(self, voice_id: str) -> None:
        """
        轮询查询音色状态（私有方法）
        
        Args:
            voice_id: 音色 ID
        
        Raises:
            RuntimeError: 当音色处理失败或轮询超时时
        """
        print("\n--- Step 2: Polling for voice status ---")
        for attempt in range(self.max_attempts):
            try:
                voice_info = self.service.query_voice(voice_id=voice_id)
                status = voice_info.get("status")
                print(f"Attempt {attempt + 1}/{self.max_attempts}: Voice status is '{status}'")
                
                if status == "OK":
                    print("Voice is ready for synthesis.")
                    return
                elif status == "UNDEPLOYED":
                    error_msg = f"Voice processing failed with status: {status}. Please check audio quality or contact support."
                    print(error_msg)
                    raise RuntimeError(error_msg)
                # 对于 "DEPLOYING" 等中间状态，继续等待
                time.sleep(self.poll_interval)
            except RuntimeError:
                raise
            except Exception as e:
                print(f"Error during status polling: {e}")
                time.sleep(self.poll_interval)
        else:
            error_msg = "Polling timed out. The voice is not ready after several attempts."
            print(error_msg)
            raise RuntimeError(error_msg)
    
    def _ensure_object_pool(self):
        """
        确保对象池已初始化（延迟初始化）
        如果初始化失败，将降级到非对象池模式
        
        Returns:
            bool: 对象池是否可用
        """
        if not self.use_object_pool:
            return False
        
        # 如果已经初始化失败，不再尝试
        if self._object_pool_init_failed:
            return False
        
        # 如果已经初始化成功，直接返回
        if self._object_pool_initialized and self.object_pool:
            return True
        
        # 尝试初始化对象池
        try:
            print(f"正在初始化对象池（延迟初始化），池大小: {self.pool_size}...")
            self.object_pool = SpeechSynthesizerObjectPool(max_size=self.pool_size)
            self._object_pool_initialized = True
            print(f"对象池初始化成功，池大小: {self.pool_size}")
            return True
        except Exception as e:
            print(f"警告: 对象池初始化失败: {e}")
            print("将降级到非对象池模式（每次创建新连接）")
            self._object_pool_init_failed = True
            self.object_pool = None
            self.use_object_pool = False  # 自动禁用对象池
            return False
    
    def _synthesize_speech(self, voice_id: str, text: str) -> bytes:
        """
        使用复刻音色进行语音合成（私有方法）
        支持对象池模式以提高高并发场景下的性能
        
        Args:
            voice_id: 音色 ID
            text: 要合成的文本
        
        Returns:
            二进制音频数据
        
        Raises:
            Exception: 当语音合成失败时
        """
        print("\n--- Step 3: Synthesizing speech with the new voice ---")
        synthesizer = None
        try:
            # 确保对象池已初始化（延迟初始化）
            pool_available = self._ensure_object_pool()
            
            if pool_available and self.object_pool:
                # 从对象池中借用 synthesizer
                print("从对象池获取 SpeechSynthesizer 对象...")
                synthesizer = self.object_pool.borrow_synthesizer(
                    model=self.target_model,
                    voice=voice_id
                )
                print("已从对象池获取对象，开始合成...")
            else:
                # 不使用对象池，直接创建新对象
                print("创建新的 SpeechSynthesizer 对象...")
                synthesizer = SpeechSynthesizer(model=self.target_model, voice=voice_id)
            
            # 执行语音合成
            audio_data = synthesizer.call(text)
            print(f"Speech synthesis successful. Request ID: {synthesizer.get_last_request_id()}")
            
            # 成功时归还对象到池中
            if self.object_pool and not self._object_pool_init_failed:
                try:
                    self.object_pool.return_synthesizer(synthesizer)
                    print("已归还 SpeechSynthesizer 对象到对象池")
                except Exception as return_error:
                    print(f"归还对象到池时出错: {return_error}")
                    # 归还失败时关闭连接
                    try:
                        synthesizer.close()
                    except Exception:
                        pass
            
            return audio_data
            
        except Exception as e:
            print(f"Error during speech synthesis: {e}")
            # 失败时处理对象
            if synthesizer:
                if self.object_pool and not self._object_pool_init_failed:
                    # 失败时不归还对象，关闭连接并丢弃
                    try:
                        synthesizer.close()
                        print("已关闭失败的 SpeechSynthesizer 连接，对象已废弃")
                    except Exception as close_error:
                        print(f"关闭连接时出错: {close_error}")
                else:
                    # 非对象池模式，直接关闭
                    try:
                        synthesizer.close()
                    except Exception:
                        pass
            raise e


def main():
    """主函数：解析命令行参数并执行语音合成"""
    parser = argparse.ArgumentParser(
        description="CosyVoice V3 语音合成工具 - 使用音频URL克隆音色并合成语音",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本用法（通过命令行参数）
  python cosyvoice_v3.py --audio-url "https://example.com/audio.wav" --text "你好世界" --output "output.mp3"
  
  # 使用环境变量中的API Key
  export DASHSCOPE_API_KEY="sk-your-key"
  python cosyvoice_v3.py --audio-url "https://example.com/audio.wav" --text "你好世界"
  
  # 通过命令行传入API Key
  python cosyvoice_v3.py --api-key "sk-your-key" --audio-url "https://example.com/audio.wav" --text "你好世界"
        """
    )
    
    parser.add_argument(
        "--audio-url",
        dest="audio_url",
        type=str,
        required=True,
        help="音频URL：公网可访问的音频文件地址，用于音色克隆"
    )
    
    parser.add_argument(
        "--text",
        "--text-to-synthesize",
        dest="text_to_synthesize",
        type=str,
        required=True,
        help="要合成的文本内容"
    )
    
    parser.add_argument(
        "--output",
        "--output-file",
        dest="output_file",
        type=str,
        default="outputs/cosyvoice_output.mp3",
        help="输出文件路径（默认: outputs/cosyvoice_output.mp3）"
    )
    
    parser.add_argument(
        "--api-key",
        dest="api_key",
        type=str,
        default=None,
        help="DashScope API Key（可选，如果不提供则从环境变量 DASHSCOPE_API_KEY 读取）"
    )
    
    parser.add_argument(
        "--voice-prefix",
        dest="voice_prefix",
        type=str,
        default="lxvoice",
        help="音色前缀（默认: lxvoice）"
    )
    
    parser.add_argument(
        "--max-attempts",
        dest="max_attempts",
        type=int,
        default=30,
        help="轮询最大尝试次数（默认: 30）"
    )
    
    parser.add_argument(
        "--poll-interval",
        dest="poll_interval",
        type=int,
        default=10,
        help="轮询间隔秒数（默认: 10）"
    )
    
    parser.add_argument(
        "--pool-size",
        dest="pool_size",
        type=int,
        default=20,
        help="对象池大小（默认: 20，建议设置为峰值并发数的 1.5 至 2 倍，范围: 1-100）"
    )
    
    parser.add_argument(
        "--no-object-pool",
        dest="use_object_pool",
        action="store_false",
        default=True,
        help="禁用对象池（默认启用对象池以提高高并发性能）"
    )
    
    args = parser.parse_args()
    
    # 执行语音合成
    print("=" * 60)
    print("CosyVoice V3 语音合成工具")
    print("=" * 60)
    
    try:
        # 创建客户端
        print("\n正在初始化客户端...")
        client = CosyVoiceV3(
            api_key=args.api_key,
            voice_prefix=args.voice_prefix,
            max_attempts=args.max_attempts,
            poll_interval=args.poll_interval,
            pool_size=args.pool_size,
            use_object_pool=args.use_object_pool
        )
        
        # 显示参数信息
        print(f"\n音频URL: {args.audio_url}")
        text_preview = args.text_to_synthesize[:50] + "..." if len(args.text_to_synthesize) > 50 else args.text_to_synthesize
        print(f"合成文本: {text_preview}")
        print(f"输出文件: {args.output_file}")
        print("\n开始处理，请稍候...\n")
        
        # 执行合成
        audio_data = client.synthesize(
            audio_url=args.audio_url,
            text_to_synthesize=args.text_to_synthesize,
            output_file=args.output_file
        )
        
        # 完成
        print("\n" + "=" * 60)
        print("✓ 语音合成成功！")
        print(f"✓ 音频已保存到: {args.output_file}")
        print(f"✓ 音频大小: {len(audio_data)} 字节")
        if args.use_object_pool:
            print(f"✓ 对象池模式: 已启用（池大小: {args.pool_size}）")
        print("=" * 60)
        
        # 清理：关闭对象池（如果使用且已初始化）
        if args.use_object_pool and client.object_pool and client._object_pool_initialized:
            try:
                client.object_pool.shutdown()
                print("对象池已关闭")
            except Exception as shutdown_error:
                print(f"关闭对象池时出错: {shutdown_error}")
        
    except ValueError:
        print("\n" + "=" * 60)
        print("✗ 错误: API Key 未设置")
        print("=" * 60)
        print("\n解决方法：")
        print("方法1: 设置环境变量（推荐）")
        print('  export DASHSCOPE_API_KEY="sk-your-api-key-here"')
        print("\n方法2: 使用命令行参数")
        print('  python cosyvoice_v3.py --api-key "sk-your-key" ...')
        print("=" * 60)
        raise
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("✗ 发生错误")
        print("=" * 60)
        print(f"错误信息: {e}")
        print("=" * 60)
        raise


if __name__ == "__main__":
    main()