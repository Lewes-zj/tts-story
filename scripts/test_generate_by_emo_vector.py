#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 generate_by_emo_vector.py 中的方法是否可以成功执行
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.generate_by_emo_vector import generate_speech_from_emo_vectors, generate_dual_speech_from_emo_config


def test_generate_speech_from_emo_vectors():
    """测试 generate_speech_from_emo_vectors 方法"""
    print("开始测试 generate_speech_from_emo_vectors 方法...")
    
    # 示例参数列表（请根据实际情况修改路径和参数）
    params_list = [
        {
            "text": "你好，这是一个测试。",
            "spk_audio_prompt": "/path/to/your/spk_audio_prompt.wav",  # 请替换为实际的音频文件路径
            "emo_alpha": 0.65,
            "emo_vector": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            "emo_audio_prompt": "/path/to/your/emo_audio_prompt.wav",  # 可选，可替换为实际的音频文件路径
            "verbose": True
        }
    ]
    
    try:
        result = generate_speech_from_emo_vectors(params_list)
        print("generate_speech_from_emo_vectors 执行成功!")
        print(f"结果: {result}")
        return True
    except Exception as e:
        print(f"generate_speech_from_emo_vectors 执行失败: {e}")
        return False


def test_generate_dual_speech_from_emo_config():
    """测试 generate_dual_speech_from_emo_config 方法"""
    print("\n开始测试 generate_dual_speech_from_emo_config 方法...")
    
    # 示例参数（请根据实际情况修改路径和参数）
    input_audio = "/path/to/your/input_audio.wav"  # 请替换为实际的音频文件路径
    text = "你好，这是一个测试。"
    spk_emo_vector = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    spk_emo_alpha = 0.7
    emo_vector = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    emo_alpha = 0.65
    
    try:
        spk_output_path, emo_output_path = generate_dual_speech_from_emo_config(
            input_audio, text, spk_emo_vector, spk_emo_alpha, emo_vector, emo_alpha
        )
        print("generate_dual_speech_from_emo_config 执行成功!")
        print(f"SPK输出路径: {spk_output_path}")
        print(f"EMO输出路径: {emo_output_path}")
        return True
    except Exception as e:
        print(f"generate_dual_speech_from_emo_config 执行失败: {e}")
        return False


def main():
    """主函数"""
    print("开始执行 generate_by_emo_vector.py 方法测试...")
    
    # 测试 generate_speech_from_emo_vectors
    test1_success = test_generate_speech_from_emo_vectors()
    
    # 测试 generate_dual_speech_from_emo_config
    test2_success = test_generate_dual_speech_from_emo_config()
    
    print("\n测试结果总结:")
    print(f"generate_speech_from_emo_vectors: {'通过' if test1_success else '失败'}")
    print(f"generate_dual_speech_from_emo_config: {'通过' if test2_success else '失败'}")
    
    if test1_success and test2_success:
        print("\n所有测试通过!")
    else:
        print("\n部分测试失败，请检查错误信息。")


if __name__ == "__main__":
    main()