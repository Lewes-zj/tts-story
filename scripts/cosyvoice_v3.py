#!/usr/bin/env python3.10
"""
CosyVoice V3 语音合成脚本
支持对象池复用 (Object Pooling) 以解决高并发下的 WebSocket 断连问题
"""

import os
import time
import argparse
import yaml
from typing import Optional, Union
import dashscope
from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer, SpeechSynthesizerObjectPool

def _load_config_model() -> Optional[str]:
    """
    从配置文件中加载 cosyvoice_model
    """
    try:
        # 获取项目根目录 (假设当前脚本在 scripts/ 目录下)
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
        """
        # 设置 API Key
        if api_key:
            dashscope.api_key = api_key
        else:
            dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
        
        if not dashscope.api_key:
            # 尝试从环境变量再次读取，防止外部未传递
            dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
            if not dashscope.api_key:
                raise ValueError("API key is required. Set DASHSCOPE_API_KEY or pass api_key parameter.")
        
        # 模型配置
        if target_model is None:
            config_model = _load_config_model()
            self.target_model = config_model if config_model else "cosyvoice-v3-plus"
        else:
            self.target_model = target_model
            
        self.voice_prefix = voice_prefix
        self.max_attempts = max_attempts
        self.poll_interval = poll_interval
        self.service = VoiceEnrollmentService()
        
        # 对象池配置
        self.pool_size = pool_size
        self.use_object_pool = use_object_pool
        self.object_pool: Optional[SpeechSynthesizerObjectPool] = None
        self._object_pool_initialized = False
        self._object_pool_init_failed = False

    def synthesize(
        self,
        audio_url: str,
        text_to_synthesize: str,
        output_file: Optional[str] = None
    ) -> bytes:
        """
        核心方法：复刻音色 -> 轮询状态 -> 合成语音
        """
        # 1. 创建音色
        voice_id = self._create_voice(audio_url)
        
        # 2. 轮询音色状态
        self._poll_voice_status(voice_id)
        
        # 3. 语音合成 (使用对象池)
        audio_data = self._synthesize_speech(voice_id, text_to_synthesize)
        
        # 4. 保存文件
        if output_file:
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"Audio saved to {output_file}")
        
        return audio_data
    
    def shutdown(self):
        """
        显式关闭对象池资源
        """
        if self.object_pool:
            try:
                # 注意：目前 SDK 可能没有公开 shutdown 方法，这里做防御性编程
                # 如果未来 SDK 支持 shutdown，这里可以直接调用
                print("Shutting down CosyVoice object pool...")
                self.object_pool = None
                self._object_pool_initialized = False
            except Exception as e:
                print(f"Error shutting down pool: {e}")

    def _create_voice(self, audio_url: str) -> str:
        """Step 1: 创建复刻任务"""
        print(f"--- Step 1: Creating voice enrollment ({self.target_model}) ---")
        try:
            voice_id = self.service.create_voice(
                target_model=self.target_model,
                prefix=self.voice_prefix,
                url=audio_url
            )
            print(f"Enrollment Request ID: {self.service.get_last_request_id()}")
            print(f"Generated Voice ID: {voice_id}")
            return voice_id
        except Exception as e:
            print(f"Error during voice creation: {e}")
            raise e
    
    def _poll_voice_status(self, voice_id: str) -> None:
        """Step 2: 轮询直到模型就绪"""
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
                    error_msg = f"Voice processing failed: {status}"
                    raise RuntimeError(error_msg)
                
                time.sleep(self.poll_interval)
            except RuntimeError:
                raise
            except Exception as e:
                print(f"Polling error: {e}, retrying...")
                time.sleep(self.poll_interval)
        else:
            raise RuntimeError("Polling timed out.")

    def _ensure_object_pool(self) -> bool:
        """延迟初始化对象池"""
        if not self.use_object_pool or self._object_pool_init_failed:
            return False
        
        if self._object_pool_initialized and self.object_pool:
            return True
        
        try:
            print(f"Initializing Object Pool (Size: {self.pool_size})...")
            # 初始化对象池
            self.object_pool = SpeechSynthesizerObjectPool(max_size=self.pool_size)
            self._object_pool_initialized = True
            print("Object Pool initialized successfully.")
            return True
        except Exception as e:
            print(f"Warning: Failed to init object pool: {e}")
            self._object_pool_init_failed = True
            self.use_object_pool = False
            return False
    
    def _synthesize_speech(self, voice_id: str, text: str) -> bytes:
        """Step 3: 合成语音 (核心优化部分)"""
        print("\n--- Step 3: Synthesizing speech ---")
        synthesizer = None
        used_pool = False
        
        try:
            # 尝试从对象池获取
            if self._ensure_object_pool():
                try:
                    # borrow_synthesizer 可能会阻塞或者失败
                    synthesizer = self.object_pool.borrow_synthesizer(
                        model=self.target_model,
                        voice=voice_id
                    )
                    used_pool = True
                    print("Synthesizer borrowed from pool.")
                except Exception as e:
                    print(f"Warning: Failed to borrow from pool ({e}), creating new instance.")
                    used_pool = False
            
            # 如果没用池（或者池借用失败），则创建新实例
            if not synthesizer:
                synthesizer = SpeechSynthesizer(model=self.target_model, voice=voice_id)
                print("Created new transient Synthesizer instance.")
            
            # 执行合成
            # 如果这里报 WebSocket closed，会被外层捕获
            audio_data = synthesizer.call(text)
            print(f"Synthesis success. Request ID: {synthesizer.get_last_request_id()}")
            
            # 成功后归还对象到池中
            if used_pool and self.object_pool:
                try:
                    self.object_pool.return_synthesizer(synthesizer)
                    print("Synthesizer returned to pool.")
                except Exception as e:
                    print(f"Error returning to pool: {e}")
                    # 归还失败则尝试关闭
                    try:
                        synthesizer.close()
                    except:
                        pass
            elif not used_pool:
                # 如果不是池中的对象，用完即关闭
                try:
                    synthesizer.call(text) # Ensure stream closed if needed, usually call returns bytes directly
                except:
                    pass
            
            return audio_data
            
        except Exception as e:
            print(f"Error during synthesis: {e}")
            
            # 发生异常时，如果是池中借出的对象，不要归还（因为它可能坏了），直接关闭
            if synthesizer:
                try:
                    synthesizer.close()
                    print("Broken synthesizer connection closed.")
                except:
                    pass
            raise e


def main():
    """CLI 入口，用于测试"""
    parser = argparse.ArgumentParser(description="CosyVoice V3 CLI Tool")
    parser.add_argument("--audio-url", required=True, help="Reference audio URL")
    parser.add_argument("--text", required=True, help="Text to synthesize")
    parser.add_argument("--output", default="output.mp3", help="Output filename")
    parser.add_argument("--api-key", help="DashScope API Key")
    parser.add_argument("--pool-size", type=int, default=5, help="Test pool size")
    
    args = parser.parse_args()
    
    try:
        client = CosyVoiceV3(api_key=args.api_key, pool_size=args.pool_size)
        
        print(f"Start processing...")
        client.synthesize(args.audio_url, args.text, args.output)
        
        # 测试完毕显式关闭，虽非必须但由于是 CLI 运行
        client.shutdown()
        
    except Exception as e:
        print(f"Fatal Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()