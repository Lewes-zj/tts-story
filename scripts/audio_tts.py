import time
import os

# 从工具模块导入TTS相关函数
from scripts.tts_utils import initialize_tts_model

# 确保输出目录存在
os.makedirs("outputs", exist_ok=True)

text = "爸爸说：“我们呀，得去买一小块毯子。”"
timestamp_ms = int(time.time() * 1000)
output_path = f"outputs/{timestamp_ms}.wav"

# 初始化TTS模型
tts = initialize_tts_model()

# 检查TTS模型是否成功初始化
if tts is not None:
    tts.infer(
        spk_audio_prompt="/root/autodl-tmp/uploads/clean_output.wav",
        text=text,
        # emo_audio_prompt="/root/index-tts/outputs/slicer_opt/11月3日.MP3_0015124800_0015277120.wav",
        output_path=output_path,
        emo_alpha=0.65,
        verbose=True,
    )
else:
    print("TTS模型初始化失败，无法生成音频。")