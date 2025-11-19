import time
from indextts.infer_v2 import IndexTTS2

# 添加音频处理库
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("警告: 未安装 pydub 库，无法合并音频文件")

tts = IndexTTS2(
    cfg_path="/root/autodl-tmp/index-tts/checkpoints/config.yaml",
    model_dir="/root/autodl-tmp/index-tts/checkpoints",
    use_fp16=False,
    use_cuda_kernel=False,
    use_deepspeed=False,
)

# timestamp_ms = int(time.time() * 1000)
interval_silence = 100

# 存储生成的音频文件路径
generated_audio_files = []

# 生成音频文件并保存路径
audio_file_1 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527606826_spk.wav",
    text="从前有个可爱的小姑娘，谁见了都喜欢，但最喜欢她的是她的奶奶，简直是她要什么就给她什么。",
    output_path=audio_file_1,
    emo_audio_prompt="outputs/1763527606826_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_1)

audio_file_2 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527379343_spk.wav",
    text="一次，奶奶送给小姑娘一顶用丝绒做的小红帽，戴在她的头上正好合适。",
    output_path=audio_file_2,
    emo_audio_prompt="outputs/1763527379343_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_2)

audio_file_3 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527479370_spk.wav",
    text="从此，姑娘再也不愿意戴任何别的帽子，于是大家便叫她“小红帽”。",
    output_path=audio_file_3,
    emo_audio_prompt="outputs/1763527479370_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_3)

audio_file_4 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527671743_spk.wav",
    text="一天，妈妈对小红帽说：",
    output_path=audio_file_4,
    emo_audio_prompt="outputs/1763527671743_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_4)

audio_file_5 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527606826_spk.wav",
    text="来，小红帽，这里有一块蛋糕和一瓶葡萄酒，快给奶奶送去。",
    output_path=audio_file_5,
    emo_audio_prompt="outputs/1763527606826_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_5)

audio_file_6 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527671743_spk.wav",
    text="奶奶生病了，身子很虚弱，吃了这些就会好一些的。",
    output_path=audio_file_6,
    emo_alpha=0.65,
    emo_vector=[0, 0, 0.55, 0, 0, 0, 0, 0],
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_6)

audio_file_7 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527512146_spk.wav",
    text="趁着现在天还没有热，赶紧动身吧。",
    output_path=audio_file_7,
    emo_audio_prompt="outputs/1763527512146_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_7)

audio_file_8 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527412947_spk.wav",
    text="在路上要好好走，不要跑，也不要离开大路，否则你会摔跤的，那样奶奶就什么也吃不上了。",
    output_path=audio_file_8,
    emo_audio_prompt="outputs/1763527412947_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_8)

audio_file_9 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527606826_spk.wav",
    text="到奶奶家的时候，别忘了说‘早上好’，也不要一进屋就东瞧西瞅。",
    output_path=audio_file_9,
    emo_audio_prompt="outputs/1763527606826_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_9)

audio_file_10 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527379343_spk.wav",
    text="我会小心的。",
    output_path=audio_file_10,
    emo_audio_prompt="outputs/1763527379343_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_10)

audio_file_11 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527379343_spk.wav",
    text="小红帽对妈妈说，并且还和妈妈拉手作了保证。",
    output_path=audio_file_11,
    emo_audio_prompt="outputs/1763527379343_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_11)

audio_file_12 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527671743_spk.wav",
    text="奶奶住在村子外面的森林里，离小红帽家有很长一段路。",
    output_path=audio_file_12,
    emo_audio_prompt="outputs/1763527671743_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_12)

audio_file_13 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527512146_spk.wav",
    text="小红帽刚走进森林就碰到了一条狼。",
    output_path=audio_file_13,
    emo_audio_prompt="outputs/1763527512146_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_13)

audio_file_14 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527448188_spk.wav",
    text="小红帽不知道狼是坏家伙，所以一点也不怕它。",
    output_path=audio_file_14,
    emo_audio_prompt="outputs/1763527448188_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_14)

audio_file_15 = f"outputs/{int(time.time() * 1000)}.wav"
tts.infer(
    spk_audio_prompt="outputs/1763527606826_spk.wav",
    text="你好，小红帽，",
    output_path=audio_file_15,
    emo_audio_prompt="outputs/1763527606826_emo.wav",
    interval_silence=interval_silence,
    verbose=True,
)
generated_audio_files.append(audio_file_15)

# 合并所有生成的音频文件
if PYDUB_AVAILABLE and generated_audio_files:
    print("正在合并音频文件...")
    # 创建一个空的音频段
    combined = AudioSegment.silent(duration=0)
    
    # 依次添加每个音频片段
    for audio_file in generated_audio_files:
        try:
            audio = AudioSegment.from_wav(audio_file)
            combined += audio
        except Exception as e:
            print(f"处理音频文件 {audio_file} 时出错: {e}")
    
    # 生成最终输出路径
    final_output_path = f"outputs/combined_story_{int(time.time() * 1000)}.wav"
    
    # 导出合并后的音频
    combined.export(final_output_path, format="wav")
    print(f"已生成合并的音频文件: {final_output_path}")
else:
    if not PYDUB_AVAILABLE:
        print("无法合并音频文件，因为未安装 pydub 库")
    else:
        print("没有生成任何音频文件来合并")