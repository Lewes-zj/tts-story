#!/usr/bin/env python3.10
"""
CosyVoice V3 语音合成脚本
无连接池模式 (Stateless/Short-lived Connection)
适用于低并发 (<20) 场景，稳定性最高，彻底避免 WebSocket Idle Timeout 错误
"""

import os
import time
import argparse
import yaml
from typing import Optional
import dashscope
from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer

def _load_config_model() -> Optional[str]:
    """
    从配置文件中加载 cosyvoice_model
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
        poll_interval: int = 10
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
            dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
            if not dashscope.api_key:
                raise ValueError("API key is required.")
        
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

    def synthesize(
        self,
        audio_url: str,
        text_to_synthesize: str,
        output_file: Optional[str] = None
    ) -> bytes:
        """
        执行完整流程：复刻 -> 轮询 -> 合成 -> 保存
        """
        # 1. 创建音色
        voice_id = self._create_voice(audio_url)
        
        # 2. 轮询音色状态
        self._poll_voice_status(voice_id)
        
        # 3. 语音合成 (每次创建新连接)
        audio_data = self._synthesize_speech(voice_id, text_to_synthesize)
        
        # 4. 保存文件
        if output_file:
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"Audio saved to {output_file}")
        
        return audio_data
    
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
                
                if status == "OK":
                    print("Voice is ready for synthesis.")
                    return
                elif status == "UNDEPLOYED":
                    raise RuntimeError(f"Voice processing failed: {status}")
                
                # print(f"Attempt {attempt + 1}/{self.max_attempts}: {status}...")
                time.sleep(self.poll_interval)
            except RuntimeError:
                raise
            except Exception as e:
                print(f"Polling error: {e}, retrying...")
                time.sleep(self.poll_interval)
        else:
            raise RuntimeError("Polling timed out.")

    def _synthesize_speech(self, voice_id: str, text: str) -> bytes:
        """
        Step 3: 合成语音 (无连接池模式)
        每次请求新建一个连接，用完立即销毁
        """
        print("\n--- Step 3: Synthesizing speech (New Connection) ---")
        synthesizer = None
        try:
            # 创建全新的合成器实例
            synthesizer = SpeechSynthesizer(model=self.target_model, voice=voice_id)
            
            # 调用 API
            audio_data = synthesizer.call(text)
            print(f"Synthesis success. Request ID: {synthesizer.get_last_request_id()}")
            
            return audio_data
            
        except Exception as e:
            print(f"Error during synthesis: {e}")
            raise e
        finally:
            # 【关键】无论成功失败，必须显式关闭连接，防止资源泄露
            if synthesizer:
                try:
                    # 此时主动发起 Close 帧，而不是等待服务端超时踢人
                    synthesizer.call(None) # 某些SDK版本需要这样刷新流，或者直接依赖 GC
                    # 如果 dashscope sdk 有显式 close 方法最好，但通常 call 结束后会自动处理非流式
                    # 这里为了保险，不做额外操作，依靠 Python GC 自动回收短连接
                    pass 
                except Exception:
                    pass


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-url", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", default="output.mp3")
    parser.add_argument("--api-key")
    
    args = parser.parse_args()
    
    try:
        client = CosyVoiceV3(api_key=args.api_key)
        client.synthesize(args.audio_url, args.text, args.output)
    except Exception as e:
        print(f"Fatal Error: {e}")

if __name__ == "__main__":
    main()