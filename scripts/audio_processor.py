"""音频处理工具模块
调用 extract-vocals 环境中的音频处理服务
"""

import os
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# extract-vocals 项目路径（根据实际部署位置调整）
EXTRACT_VOCALS_DIR = os.getenv(
    "EXTRACT_VOCALS_DIR", 
    "/root/autodl-tmp/extract-vocals"
)
AUDIO_PROCESSOR_SCRIPT = os.path.join(
    EXTRACT_VOCALS_DIR, 
    "audio_processor_service.py"
)


def process_audio_with_deepfilternet_denoiser(
    input_path: str, 
    output_path: Optional[str] = None,
    device: Optional[str] = None,
    timeout: int = 300
) -> Optional[str]:
    """
    使用 DeepFilterNet -> Denoiser 两步处理音频
    
    Args:
        input_path: 输入音频文件路径
        output_path: 输出音频文件路径（可选，默认在输入文件同目录下生成）
        device: 设备类型（cuda/cpu），默认自动选择
        timeout: 超时时间（秒），默认300秒
    
    Returns:
        str: 处理后的音频文件路径，失败返回 None
    """
    # 检查输入文件
    if not os.path.exists(input_path):
        logger.error(f"输入文件不存在: {input_path}")
        return None
    
    # 检查处理脚本是否存在
    if not os.path.exists(AUDIO_PROCESSOR_SCRIPT):
        logger.error(f"音频处理脚本不存在: {AUDIO_PROCESSOR_SCRIPT}")
        logger.error(f"请检查 EXTRACT_VOCALS_DIR 环境变量是否正确设置")
        return None
    
    # 如果没有指定输出路径，在输入文件同目录下生成
    if output_path is None:
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_dir = os.path.dirname(input_path)
        output_path = os.path.join(output_dir, f"{base_name}_clean.wav")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 构建命令 - 使用 extract-vocals 虚拟环境中的 Python
    venv_python = os.path.join(EXTRACT_VOCALS_DIR, "venv", "bin", "python3")
    if not os.path.exists(venv_python):
        # 如果虚拟环境不存在，回退到系统 Python
        venv_python = "python3"
        logger.warning(f"虚拟环境 Python 不存在，使用系统 Python: {venv_python}")
    
    cmd = [venv_python, AUDIO_PROCESSOR_SCRIPT, input_path, output_path]
    if device:
        cmd.extend(["--device", device])
    
    logger.info(f"开始处理音频: {input_path} -> {output_path}")
    logger.debug(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 执行处理脚本
        result = subprocess.run(
            cmd,
            cwd=EXTRACT_VOCALS_DIR,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                logger.info(
                    f"音频处理成功: {output_path} "
                    f"(大小: {file_size / 1024 / 1024:.2f} MB)"
                )
                return output_path
            else:
                logger.error(f"处理完成但输出文件不存在: {output_path}")
                logger.error(f"标准输出: {result.stdout}")
                logger.error(f"错误输出: {result.stderr}")
                return None
        else:
            logger.error(f"音频处理失败，返回码: {result.returncode}")
            logger.error(f"标准输出: {result.stdout}")
            logger.error(f"错误输出: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error(f"音频处理超时（超过 {timeout} 秒）")
        return None
    except Exception as e:
        logger.error(f"执行音频处理脚本时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

