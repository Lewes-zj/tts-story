import time
import os
import sys
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入TTS工具函数
from scripts.tts_utils import initialize_tts_model, TTS_AVAILABLE

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
    logger.info("开始执行 generate_speech_from_emo_vectors 函数")
    
    if not TTS_AVAILABLE:
        error_msg = "TTS 功能不可用，请确保已正确安装 indextts 包"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # 初始化TTS模型，配置本地路径和离线模式
    logger.info("正在初始化TTS模型...")
    tts = initialize_tts_model()
    if not tts:
        error_msg = "TTS 模型初始化失败"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info("TTS模型初始化成功")

    # 确保输出目录存在
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"确保输出目录存在: {output_dir}")

    # 为每个参数添加输出路径并执行推理
    for i, params in enumerate(params_list):
        try:
            logger.info(f"处理第 {i+1}/{len(params_list)} 个参数")
            
            # 提取必要参数
            text = params.get("text")
            spk_audio_prompt = params.get("spk_audio_prompt")
            emo_alpha = float(params.get("emo_alpha", 0.65))
            emo_vector = params.get("emo_vector", [0] * 8)

            # 可选参数
            emo_audio_prompt = params.get("emo_audio_prompt")
            output_path = params.get("output_path")
            verbose = params.get("verbose", True)

            # 验证必要参数
            if not text:
                error_msg = f"第 {i+1} 个参数缺少必需的 'text' 字段"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            if not spk_audio_prompt:
                error_msg = f"第 {i+1} 个参数缺少必需的 'spk_audio_prompt' 字段"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # 如果没有指定输出路径，则自动生成
            if not output_path:
                timestamp_ms = int(time.time() * 1000)
                output_path = f"{output_dir}/{timestamp_ms}_{i}.wav"
                # 更新参数字典中的输出路径
                params["output_path"] = output_path
                logger.info(f"为第 {i+1} 个参数自动生成输出路径: {output_path}")
            else:
                logger.info(f"第 {i+1} 个参数使用指定输出路径: {output_path}")

            # 执行推理
            logger.info(f"开始执行第 {i+1} 个参数的TTS推理")
            logger.info(f"推理参数: text={text}, spk_audio_prompt={spk_audio_prompt}, emo_audio_prompt={emo_audio_prompt}, output_path={output_path}, emo_alpha={emo_alpha}, emo_vector={emo_vector}")
            tts.infer(
                spk_audio_prompt=spk_audio_prompt,
                text=text,
                emo_audio_prompt=emo_audio_prompt,
                output_path=output_path,
                emo_alpha=emo_alpha,
                emo_vector=emo_vector,
                verbose=verbose,
            )
            logger.info(f"第 {i+1} 个参数TTS推理完成，输出路径: {output_path}")
            
        except Exception as e:
            logger.error(f"处理第 {i+1} 个参数时发生错误: {str(e)}")
            raise RuntimeError(f"处理第 {i+1} 个参数时发生错误: {str(e)}") from e

    logger.info("generate_speech_from_emo_vectors 函数执行完成")
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
    logger.info("开始执行 generate_dual_speech_from_emo_config 函数")
    
    if not TTS_AVAILABLE:
        error_msg = "TTS 功能不可用，请确保已正确安装 indextts 包"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # 初始化TTS模型，配置本地路径和离线模式
    logger.info("正在初始化TTS模型...")
    tts = initialize_tts_model()
    if not tts:
        error_msg = "TTS 模型初始化失败"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info("TTS模型初始化成功")

    # 确保输出目录存在
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"确保输出目录存在: {output_dir}")

    # 验证输入参数
    if not input_audio:
        error_msg = "缺少必需的 'input_audio' 参数"
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    if not text:
        error_msg = "缺少必需的 'text' 参数"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # 生成时间戳
    timestamp_ms = int(time.time() * 1000)
    logger.info(f"生成时间戳: {timestamp_ms}")

    try:
        # 第一次调用：使用高质量input音频的情绪向量
        spk_output_path = f"{output_dir}/{timestamp_ms}_spk.wav"
        logger.info(f"开始第一次TTS推理，输出路径: {spk_output_path}")
        logger.info(f"第一次推理参数: spk_audio_prompt={input_audio}, text={text}, output_path={spk_output_path}, emo_alpha={spk_emo_alpha}, emo_vector={spk_emo_vector}")
        tts.infer(
            spk_audio_prompt=input_audio,
            text=text,
            output_path=spk_output_path,
            emo_alpha=spk_emo_alpha,
            emo_vector=spk_emo_vector,
            verbose=True,
        )
        logger.info(f"第一次TTS推理完成，输出路径: {spk_output_path}")

        # 第二次调用：使用情绪引导音频的情绪向量
        emo_output_path = f"{output_dir}/{timestamp_ms}_emo.wav"
        logger.info(f"开始第二次TTS推理，输出路径: {emo_output_path}")
        logger.info(f"第二次推理参数: spk_audio_prompt={input_audio}, text={text}, output_path={emo_output_path}, emo_alpha={emo_alpha}, emo_vector={emo_vector}")
        tts.infer(
            spk_audio_prompt=input_audio,
            text=text,
            output_path=emo_output_path,
            emo_alpha=emo_alpha,
            emo_vector=emo_vector,
            verbose=True,
        )
        logger.info(f"第二次TTS推理完成，输出路径: {emo_output_path}")

        logger.info("generate_dual_speech_from_emo_config 函数执行完成")
        return spk_output_path, emo_output_path
        
    except Exception as e:
        error_msg = f"TTS推理过程中发生错误: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    