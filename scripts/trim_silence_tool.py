#!/usr/bin/env python3
"""
音频静音去除工具 (trim_silence_tool.py)
功能：批量扫描文件夹中的音频文件，自动去除首尾的静音部分，并保存到输出目录。

用法：
    python trim_silence_tool.py -i [输入文件夹] -o [输出文件夹]

参数：
    -i, --input: 输入音频文件夹路径
    -o, --output: 输出音频文件夹路径 (默认: output_trimmed)
    --thresh: 静音阈值 (dBFS), 默认 -40
    --chunk: 检测分块大小 (ms), 默认 10
"""

import os
import sys
import argparse
import logging
from tqdm import tqdm

try:
    from pydub import AudioSegment
    from pydub.silence import detect_leading_silence
except ImportError:
    print("错误：请先安装 pydub")
    print("运行: pip install pydub")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def trim_silence(audio: AudioSegment, silence_thresh: int = -40, chunk_size: int = 10):
    """
    去除音频首尾的静音部分
    """
    if len(audio) == 0:
        return audio, 0

    def detect_silence_end(audio_segment):
        return detect_leading_silence(
            audio_segment, silence_threshold=silence_thresh, chunk_size=chunk_size
        )

    # 检测开头静音
    start_trim = detect_silence_end(audio)

    # 检测结尾静音 (反转音频后检测开头)
    end_trim = detect_silence_end(audio.reverse())

    original_duration = len(audio)

    # 如果全是静音，保留一点点以免出错
    if start_trim + end_trim >= original_duration:
        return audio[0:0], original_duration / 1000.0

    trimmed = audio[start_trim : original_duration - end_trim]
    saved_seconds = (start_trim + end_trim) / 1000.0

    return trimmed, saved_seconds


def process_folder(input_dir, output_dir, thresh=-40, chunk=10):
    """批量处理文件夹"""
    if not os.path.exists(input_dir):
        logger.error(f"❌ 输入文件夹不存在: {input_dir}")
        return

    os.makedirs(output_dir, exist_ok=True)

    # 支持的格式
    extensions = (".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac")

    files = [f for f in os.listdir(input_dir) if f.lower().endswith(extensions)]
    total_files = len(files)

    if total_files == 0:
        logger.warning(f"⚠️  在 {input_dir} 中未找到音频文件")
        return

    logger.info(f"📂 正在处理: {input_dir}")
    logger.info(f"   目标: {output_dir}")
    logger.info(f"   文件数: {total_files}")
    logger.info("-" * 40)

    success_count = 0
    total_saved_time = 0.0

    for filename in tqdm(files, unit="file"):
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        try:
            # 加载音频
            audio = AudioSegment.from_file(input_path)
            orig_len = len(audio) / 1000.0

            # 去除静音
            trimmed_audio, saved_time = trim_silence(
                audio, silence_thresh=thresh, chunk_size=chunk
            )
            new_len = len(trimmed_audio) / 1000.0

            # 只有当确实有变化，或者为了统一格式时才保存
            # 这里默认全部保存到输出目录

            # 导出 (保持原格式，如果是 mp3 可能需要指定 format)
            fmt = os.path.splitext(filename)[1][1:].lower()
            if fmt == "m4a":
                fmt = "ipod"  # pydub specific

            trimmed_audio.export(output_path, format=fmt)

            success_count += 1
            total_saved_time += saved_time

            # logger.info(f"✅ {filename}: {orig_len:.2f}s -> {new_len:.2f}s (减去 {saved_time:.2f}s)")

        except Exception as e:
            logger.error(f"❌ 处理失败 {filename}: {e}")

    logger.info("-" * 40)
    logger.info(f"🎉 完成! 成功处理: {success_count}/{total_files}")
    logger.info(f"📉 总共减去了 {total_saved_time:.2f} 秒的静音")


# ============================================================================
# API 调用函数 (用于 FastAPI 集成)
# ============================================================================


def run_trim_silence(
    input_dir: str, output_dir: str, silence_thresh: int = -40
) -> dict:
    """
    批量去除音频静音 (用于API调用)

    Args:
        input_dir (str): 输入音频文件夹路径
        output_dir (str): 输出音频文件夹路径
        silence_thresh (int): 静音阈值 (dBFS), 默认 -40

    Returns:
        dict: 处理结果
            - input_dir: 输入目录路径
            - output_dir: 输出目录路径
            - total_files: 总文件数
            - success_count: 成功处理数量
            - failed_count: 失败数量
            - total_saved_time: 总共去除的静音时长(秒)

    Raises:
        FileNotFoundError: 当输入目录不存在时
    """
    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"输入文件夹不存在: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)

    # 支持的格式
    extensions = (".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac")
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(extensions)]
    total_files = len(files)

    if total_files == 0:
        logger.warning(f"⚠️  在 {input_dir} 中未找到音频文件")
        return {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "total_files": 0,
            "success_count": 0,
            "failed_count": 0,
            "total_saved_time": 0.0,
        }

    logger.info(f"📂 正在处理: {input_dir}")
    logger.info(f"   目标: {output_dir}")
    logger.info(f"   文件数: {total_files}")
    logger.info("-" * 40)

    success_count = 0
    failed_count = 0
    total_saved_time = 0.0

    for filename in tqdm(files, unit="file"):
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        try:
            # 加载音频
            audio = AudioSegment.from_file(input_path)

            # 去除静音
            trimmed_audio, saved_time = trim_silence(
                audio, silence_thresh=silence_thresh, chunk_size=10
            )

            # 导出 (保持原格式)
            fmt = os.path.splitext(filename)[1][1:].lower()
            if fmt == "m4a":
                fmt = "ipod"  # pydub specific

            trimmed_audio.export(output_path, format=fmt)

            success_count += 1
            total_saved_time += saved_time

        except Exception as e:
            logger.error(f"❌ 处理失败 {filename}: {e}")
            failed_count += 1

    logger.info("-" * 40)
    logger.info(f"🎉 完成! 成功处理: {success_count}/{total_files}")
    logger.info(f"📉 总共减去了 {total_saved_time:.2f} 秒的静音")

    return {
        "input_dir": input_dir,
        "output_dir": output_dir,
        "total_files": total_files,
        "success_count": success_count,
        "failed_count": failed_count,
        "total_saved_time": round(total_saved_time, 2),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量音频去静音工具")
    parser.add_argument("-i", "--input", required=True, help="输入音频文件夹")
    parser.add_argument("-o", "--output", default="output_trimmed", help="输出文件夹")
    parser.add_argument(
        "--thresh", type=int, default=-40, help="静音阈值 (dBFS), 默认 -40"
    )

    args = parser.parse_args()

    process_folder(args.input, args.output, thresh=args.thresh)
