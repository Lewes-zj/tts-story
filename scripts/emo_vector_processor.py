"""
情绪向量处理器
查询数据库表emo_vector_config的数据，生成参数列表并调用TTS生成方法
"""

import sys
import os
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        logger.info(f"初始化EmoVectorProcessor，配置路径: {config_path}")
        # 创建情绪向量配置DAO实例
        self.emo_dao = EmoVectorConfigDAO(config_path)
        logger.info("EmoVectorProcessor初始化完成")

    def _parse_vector_string(self, vector_str):
        """
        解析向量字符串为列表

        Args:
            vector_str (str): 向量字符串，格式如 "[0, 0, 0.5, 0, 0, 0, 0, 0]"

        Returns:
            list: 向量数值列表
        """
        logger.debug(f"解析向量字符串: {vector_str}")
        # 移除方括号并分割
        vector_str = vector_str.strip().strip("[]")
        # 分割并转换为浮点数
        result = [float(x.strip()) for x in vector_str.split(",") if x.strip()]
        logger.debug(f"解析结果: {result}")
        return result

    def process_emo_vectors(self, input_audio, text):
        """
        处理情绪向量数据，查询数据库并生成TTS参数列表

        Args:
            input_audio (str): 用户纯净音频路径
            text (str): 文本内容

        Returns:
            list: 包含生成结果的字典列表
        """
        logger.info("开始处理情绪向量数据")
        logger.info(f"输入音频路径: {input_audio}")
        logger.info(f"文本内容: {text}")
        
        # 查询数据库获取情绪向量配置
        logger.info("查询数据库获取情绪向量配置...")
        emo_configs = self.emo_dao.fetch_all_configs()
        logger.info(f"从数据库获取到{len(emo_configs)}个情绪配置")
        
        if not emo_configs:
            logger.warning("未从数据库获取到任何情绪配置")
            return []

        # 生成结果列表
        result_list = []
        
        # 遍历每个情绪配置
        for i, config in enumerate(emo_configs):
            logger.info(f"处理第{i+1}/{len(emo_configs)}个情绪配置，类型: {config['type']}")
            
            # 解析情绪向量
            logger.debug(f"解析spk_emo_vector: {config['spk_emo_vector']}")
            spk_emo_vector = self._parse_vector_string(config["spk_emo_vector"])
            logger.debug(f"解析emo_vector: {config['emo_vector']}")
            emo_vector = self._parse_vector_string(config["emo_vector"])

            # 获取情绪混合系数
            logger.debug(f"获取spk_emo_alpha: {config['spk_emo_alpha']}")
            spk_emo_alpha = float(config["spk_emo_alpha"])
            logger.debug(f"获取emo_alpha: {config['emo_alpha']}")
            emo_alpha = float(config["emo_alpha"])
            
            logger.info(f"开始调用TTS生成音频，情绪类型: {config['type']}")
            # 调用TTS生成两种不同类型的音频文件
            spk_output_path, emo_output_path = generate_dual_speech_from_emo_config(
                input_audio=input_audio,
                text=text,
                spk_emo_vector=spk_emo_vector,
                spk_emo_alpha=spk_emo_alpha,
                emo_vector=emo_vector,
                emo_alpha=emo_alpha,
            )
            logger.info(f"TTS生成完成，spk_output_path: {spk_output_path}, emo_output_path: {emo_output_path}")

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
            logger.info(f"第{i+1}/{len(emo_configs)}个情绪配置处理完成")

        logger.info(f"所有情绪向量处理完成，共生成{len(result_list)}个结果")
        return result_list