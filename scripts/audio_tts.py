import time

# 从工具模块导入TTS相关函数
from scripts.tts_utils import initialize_tts_model

# 初始化TTS模型
tts = initialize_tts_model(
    cfg_path="/root/index-tts/checkpoints/config.yaml",
    model_dir="/root/index-tts/checkpoints"
)

text = "爸爸说：“我们呀，得去买一小块毯子。”"
timestamp_ms = int(time.time() * 1000)
output_path = f"outputs/{timestamp_ms}.wav"
tts.infer(
    spk_audio_prompt="/tmp/gradio/1429929264483176a0ce6c0a04265af5d2405df270e78d0fbbda2ebcaadf9db9/audio_20251024_150110.wav",
    text=text,
    emo_audio_prompt="/root/index-tts/outputs/slicer_opt/11月3日.MP3_0015124800_0015277120.wav",
    output_path=output_path,
    emo_alpha=0.65,
    verbose=True,
)