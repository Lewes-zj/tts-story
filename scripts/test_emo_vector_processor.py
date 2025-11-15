"""
测试情绪向量处理器
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.emo_vector_processor import EmoVectorProcessor


def test_emo_vector_processor():
    """测试情绪向量处理器"""
    # 创建处理器实例
    processor = EmoVectorProcessor()

    # 测试数据
    input_audio = "/path/to/input/audio.wav"
    text = "这是一个测试文本"

    # 处理情绪向量
    try:
        result_list = processor.process_emo_vectors(input_audio, text)
        print("处理结果:")
        for result in result_list:
            print(f"  情绪类型: {result['emo_type']}")
            print(f"  文本: {result['text']}")
            print(f"  SPK音频路径: {result['spk_audio_prompt']}")
            print(f"  SPK情绪向量: {result['spk_emo_vector']}")
            print(f"  SPK情绪系数: {result['spk_emo_alpha']}")
            print(f"  EMO音频路径: {result['emo_audio_prompt']}")
            print(f"  EMO情绪向量: {result['emo_vector']}")
            print(f"  EMO情绪系数: {result['emo_alpha']}")
            print()
    except Exception as e:
        print(f"处理过程中发生错误: {e}")


if __name__ == "__main__":
    test_emo_vector_processor()
