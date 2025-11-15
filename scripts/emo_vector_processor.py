"""
情绪向量处理器
查询数据库表emo_vector_config的数据，生成参数列表并调用TTS生成方法
"""

import sys
import os

# 添加项目根目录到Python路径，确保能正确导入indextts相关模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
import json
import os

# 导入TTS生成方法
from scripts.generate_by_emo_vector import generate_dual_speech_from_emo_config

# 导入情绪向量配置DAO
from scripts.emo_vector_config_dao import EmoVectorConfigDAO


class EmoVectorProcessor:
    """情绪向量处理器类"""

    def __init__(self, config_path="config/database.yaml"):
        """
        初始化情绪向量处理器

        Args:
            config_path (str): 数据库配置文件路径
        """
        # 创建情绪向量配置DAO实例
        self.emo_dao = EmoVectorConfigDAO(config_path)

    def _parse_vector_string(self, vector_str):
        """
        解析向量字符串为列表

        Args:
            vector_str (str): 向量字符串，格式如 "[0, 0, 0.5, 0, 0, 0, 0, 0]"

        Returns:
            list: 向量数值列表
        """
        # 移除方括号并分割
        vector_str = vector_str.strip().strip("[]")
        # 分割并转换为浮点数
        return [float(x.strip()) for x in vector_str.split(",") if x.strip()]

    def process_emo_vectors(self, input_audio, text):
        """
        处理情绪向量数据，查询数据库并生成TTS参数列表

        Args:
            input_audio (str): 用户纯净音频路径
            text (str): 文本内容

        Returns:
            list: 包含生成结果的字典列表
        """
        # 查询数据库获取情绪向量配置
        emo_configs = self.emo_dao.fetch_all_configs()

        # 生成结果列表
        result_list = []

        # 遍历每个情绪配置
        for config in emo_configs:
            # 解析情绪向量
            spk_emo_vector = self._parse_vector_string(config["spk_emo_vector"])
            emo_vector = self._parse_vector_string(config["emo_vector"])

            # 获取情绪混合系数
            spk_emo_alpha = float(config["spk_emo_alpha"])
            emo_alpha = float(config["emo_alpha"])

            # 调用TTS生成两种不同类型的音频文件
            spk_output_path, emo_output_path = generate_dual_speech_from_emo_config(
                input_audio=input_audio,
                text=text,
                spk_emo_vector=spk_emo_vector,
                spk_emo_alpha=spk_emo_alpha,
                emo_vector=emo_vector,
                emo_alpha=emo_alpha,
            )

            # 构造结果字典
            result = {
                "emo_type": config["type"],
                "text": text,
                "spk_audio_prompt": spk_output_path,
                "spk_emo_vector": config["spk_emo_vector"],
                "spk_emo_alpha": spk_emo_alpha,
                "emo_audio_prompt": emo_output_path,
                "emo_vector": config["emo_vector"],
                "emo_alpha": emo_alpha,
            }

            result_list.append(result)

        return result_list
