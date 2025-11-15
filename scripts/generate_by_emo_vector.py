"""
根据情绪向量生成
"""

import time
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from indextts.infer_v2 import IndexTTS2
    TTS_AVAILABLE = True
except ImportError:
    print("警告: 未找到 indextts 包，TTS 功能将不可用")
    IndexTTS2 = None
    TTS_AVAILABLE = False


def generate_speech_from_emo_vectors(params_list):
    """
    根据情绪向量列表生成语音

    Args:
        params_list (list): 参数列表，每个元素为包含以下字段的字典:
            - text (str): 要转换的文本
            - spk_audio_prompt (str): 说话人音频提示路径
            - emo_alpha (float): 情绪混合系数
            - emo_vector (list): 情绪向量
            - emo_audio_prompt (str, optional): 情绪音频提示路径
            - output_path (str, optional): 输出路径，默认自动生成
            - verbose (bool, optional): 是否显示详细信息，默认True

    Returns:
        list: 包含输出路径的参数字典列表
    """
    if not TTS_AVAILABLE:
        print("错误: TTS 功能不可用，请确保已正确安装 indextts 包")
        return params_list

    # 初始化TTS模型，配置本地路径和离线模式
    tts = IndexTTS2(
        cfg_path="/root/index-tts/checkpoints/config.yaml",
        model_dir="/root/index-tts/checkpoints",
        use_fp16=False,
        use_cuda_kernel=False,
        use_deepspeed=False,
    )

    # 确保输出目录存在
    os.makedirs("outputs", exist_ok=True)

    # 为每个参数添加输出路径并执行推理
    for i, params in enumerate(params_list):
        # 提取必要参数
        text = params.get("text")
        spk_audio_prompt = params.get("spk_audio_prompt")
        emo_alpha = params.get("emo_alpha", 0.65)
        emo_vector = params.get("emo_vector", [0] * 8)

        # 可选参数
        emo_audio_prompt = params.get("emo_audio_prompt")
        output_path = params.get("output_path")
        verbose = params.get("verbose", True)

        # 如果没有指定输出路径，则自动生成
        if not output_path:
            timestamp_ms = int(time.time() * 1000)
            output_path = f"outputs/{timestamp_ms}_{i}.wav"
            # 更新参数字典中的输出路径
            params["output_path"] = output_path

        # 执行推理
        tts.infer(
            spk_audio_prompt=spk_audio_prompt,
            text=text,
            emo_audio_prompt=emo_audio_prompt,
            output_path=output_path,
            emo_alpha=emo_alpha,
            emo_vector=emo_vector,
            verbose=verbose,
        )

    return params_list


def generate_dual_speech_from_emo_config(input_audio, text, spk_emo_vector, spk_emo_alpha, emo_vector, emo_alpha):
    """
    根据情绪配置生成两种不同类型的音频文件

    Args:
        input_audio (str): 输入音频文件路径
        text (str): 要转换的文本
        spk_emo_vector (list): 高质量input音频情绪向量
        spk_emo_alpha (float): 高质量input音频情绪混合系数
        emo_vector (list): 情绪引导音频情绪向量
        emo_alpha (float): 情绪引导音频情绪混合系数

    Returns:
        tuple: (spk_output_path, emo_output_path) 两个生成的音频文件路径
    """
    if not TTS_AVAILABLE:
        print("错误: TTS 功能不可用，请确保已正确安装 indextts 包")
        return None, None

    # 初始化TTS模型，配置本地路径和离线模式
    tts = IndexTTS2(
        cfg_path="/root/index-tts/checkpoints/config.yaml",
        model_dir="/root/index-tts/checkpoints",
        use_fp16=False,
        use_cuda_kernel=False,
        use_deepspeed=False,
    )

    # 确保输出目录存在
    os.makedirs("outputs", exist_ok=True)

    # 生成时间戳
    timestamp_ms = int(time.time() * 1000)

    # 第一次调用：使用高质量input音频的情绪向量
    spk_output_path = f"outputs/{timestamp_ms}_spk.wav"
    tts.infer(
        spk_audio_prompt=input_audio,
        text=text,
        output_path=spk_output_path,
        emo_alpha=spk_emo_alpha,
        emo_vector=spk_emo_vector,
        verbose=True,
    )

    # 第二次调用：使用情绪引导音频的情绪向量
    emo_output_path = f"outputs/{timestamp_ms}_emo.wav"
    tts.infer(
        spk_audio_prompt=input_audio,
        text=text,
        output_path=emo_output_path,
        emo_alpha=emo_alpha,
        emo_vector=emo_vector,
        verbose=True,
    )

    return spk_output_path, emo_output_path