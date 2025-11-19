import time
from indextts.infer_v2 import IndexTTS2

tts = IndexTTS2(
    cfg_path="/root/autodl-tmp/index-tts/checkpoints/config.yaml",
    model_dir="/root/autodl-tmp/index-tts/checkpoints",
    use_fp16=False,
    use_cuda_kernel=False,
    use_deepspeed=False,
)

text = "爸爸说：“我们呀，得去买一小块毯子。”"
timestamp_ms = int(time.time() * 1000)
output_path = f"outputs/{timestamp_ms}.wav"
tts.infer(
    #spk_audio_prompt="/tmp/gradio/1429929264483176a0ce6c0a04265af5d2405df270e78d0fbbda2ebcaadf9db9/audio_20251024_150110.wav",
    spk_audio_prompt="/root/autodl-tmp/uploads/clean_output.wav",
    text=text,
    # emo_audio_prompt="/root/index-tts/outputs/slicer_opt/11月3日.MP3_0015124800_0015277120.wav",
    output_path=output_path,
    emo_alpha=0.65,
    verbose=True,
)