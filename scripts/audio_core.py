#!/usr/bin/env python3
"""
音频核心模块 (audio_core.py)
功能：提供音频加载、配置解析、静音裁剪等核心业务逻辑

这是一个纯函数式的核心层，不依赖于具体的应用场景。
"""

import os
import sys
import json
import logging

from dataclasses import dataclass
from typing import List, Optional, Tuple

# 尝试导入 pandas，如果只用 JSON 其实可以不需要 pandas，但为了兼容性保留
try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from pydub import AudioSegment
    from pydub.silence import detect_leading_silence
except ImportError:
    print("错误：请先安装 pydub 和 numpy")
    print("运行: pip install pydub numpy")
    sys.exit(1)

# 配置日志
logger = logging.getLogger(__name__)


# ============================================================================
# 数据类定义
# ============================================================================


@dataclass
class AudioClip:
    """音频片段数据结构"""

    id: int
    text: str
    source_start: float  # 源音频开始时间 (秒)
    source_end: float  # 源音频结束时间 (秒)
    clip_type: str  # ANCHOR 或 FLOATING
    filename: str = ""  # TTS 文件名（新格式）
    audio: Optional[AudioSegment] = None
    duration: float = 0.0
    target_start: float = 0.0  # 计算后的目标开始时间


# ============================================================================
# 音频处理函数
# ============================================================================


def trim_silence(
    audio: AudioSegment, silence_thresh: int = -40, chunk_size: int = 10
) -> Tuple[AudioSegment, float]:
    """
    去除音频首尾的静音部分

    Args:
        audio: 输入音频段
        silence_thresh: 静音阈值 (dB)，默认 -40
        chunk_size: 检测块大小 (ms)，默认 10

    Returns:
        Tuple[AudioSegment, float]: (裁剪后的音频, 节省的时长(秒))
    """
    original_duration = len(audio)

    def detect_silence_end(audio_segment):
        return detect_leading_silence(
            audio_segment, silence_threshold=silence_thresh, chunk_size=chunk_size
        )

    start_trim = detect_silence_end(audio)
    end_trim = detect_silence_end(audio.reverse())

    trimmed = audio[start_trim : original_duration - end_trim]

    if len(trimmed) < 100:  # 至少保留 100ms
        return audio, 0.0

    saved_ms = original_duration - len(trimmed)
    return trimmed, saved_ms / 1000.0


def load_tts_audio(tts_folder: str, clip_id: int, text: str) -> Optional[AudioSegment]:
    """
    加载 TTS 音频文件（通过 ID 和文本自动匹配）

    Args:
        tts_folder: TTS 音频文件夹路径
        clip_id: 片段 ID
        text: 片段文本

    Returns:
        Optional[AudioSegment]: 加载的音频，如果未找到则返回 None
    """
    patterns = [
        f"{clip_id}-{text}.wav",
        f"{clip_id}-{text}.mp3",
        f"{clip_id}.wav",
        f"{clip_id}.mp3",
    ]

    for pattern in patterns:
        file_path = os.path.join(tts_folder, pattern)
        if os.path.exists(file_path):
            logger.info(f"加载 TTS 文件: {pattern}")
            return AudioSegment.from_file(file_path)

    for file in os.listdir(tts_folder):
        if file.startswith(f"{clip_id}-") or file.startswith(f"{clip_id}_"):
            file_path = os.path.join(tts_folder, file)
            logger.info(f"加载 TTS 文件: {file}")
            return AudioSegment.from_file(file_path)

    return None


# ============================================================================
# 配置加载函数
# ============================================================================


def load_config(config_path: str) -> List[AudioClip]:
    """
    加载对齐配置文件（支持 JSON 和 Excel 格式）

    Args:
        config_path: 配置文件路径 (.json 或 .xlsx/.xls)

    Returns:
        List[AudioClip]: 音频片段列表

    Raises:
        FileNotFoundError: 如果配置文件不存在
        ValueError: 如果文件格式不支持
    """
    logger.info(f"加载配置文件: {config_path}")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"文件不存在: {config_path}")

    clips = []

    # === 1. 处理 JSON 格式 ===
    if config_path.lower().endswith(".json"):
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            # 映射 JSON 字段到 AudioClip
            # JSON keys: id, text, source_start, source_end, alignment_type, filename
            clip = AudioClip(
                id=int(item.get("id")),
                text=str(item.get("text", "")).strip(),
                source_start=float(item.get("source_start", 0.0)),
                source_end=float(item.get("source_end", 0.0)),
                # 注意：JSON里叫 alignment_type，代码里用 clip_type
                clip_type=str(item.get("alignment_type", "FLOATING")).upper().strip(),
                filename=str(item.get("filename", "")),
            )
            clips.append(clip)

    # === 2. 处理 Excel 格式 (兼容旧代码) ===
    elif config_path.lower().endswith((".xlsx", ".xls")):
        if not HAS_PANDAS:
            raise ImportError(
                "读取Excel失败：未安装pandas或openpyxl。请运行 pip install pandas openpyxl"
            )

        df = pd.read_excel(config_path, engine="openpyxl")

        for _, row in df.iterrows():
            # 兼容 Excel 的中文列名
            if "源开始时间(秒)" in df.columns:
                src_start = float(row["源开始时间(秒)"])
                src_end = float(row["源结束时间(秒)"])
                clip_type = str(row["类型"]).upper().strip()
                text = str(row["文本"]).strip()
            else:
                src_start = float(row.get("源开始(秒)", 0.0))
                src_end = float(row.get("源结束(秒)", 0.0))
                clip_type = str(row.get("对齐类型", "FLOATING")).upper().strip()
                text = str(row.get("文本", "")).strip()

            filename = str(row.get("文件名", "")) if "文件名" in df.columns else ""

            clip = AudioClip(
                id=int(row["ID"]),
                text=text,
                source_start=src_start,
                source_end=src_end,
                clip_type=clip_type,
                filename=filename,
            )
            clips.append(clip)

    else:
        raise ValueError("不支持的文件格式，仅支持 .json 或 .xlsx")

    logger.info(f"共加载 {len(clips)} 个片段")

    anchors = sum(1 for c in clips if c.clip_type == "ANCHOR")
    floating = sum(1 for c in clips if c.clip_type == "FLOATING")
    logger.info(f"锚点 (ANCHOR): {anchors} 个, 浮动块 (FLOATING): {floating} 个")

    return clips


# ============================================================================
# 音频加载函数
# ============================================================================


def load_all_tts(clips: List[AudioClip], tts_folder: str) -> bool:
    """
    加载所有 TTS 音频并去除静音

    Args:
        clips: 音频片段列表
        tts_folder: TTS 音频文件夹路径

    Returns:
        bool: 如果所有音频加载成功返回 True，否则返回 False
    """
    logger.info(f"从 {tts_folder} 加载 TTS 音频...")
    success = True
    total_saved = 0.0

    for clip in clips:
        audio = None

        # 优先使用文件名直接加载
        if clip.filename:
            file_path = os.path.join(tts_folder, clip.filename)
            if os.path.exists(file_path):
                logger.info(f"加载: {clip.filename}")
                audio = AudioSegment.from_file(file_path)
            else:
                # 如果文件名路径不对，尝试只用文件名在 tts_folder 下找
                basename = os.path.basename(clip.filename)
                file_path = os.path.join(tts_folder, basename)
                if os.path.exists(file_path):
                    logger.info(f"加载(basename): {basename}")
                    audio = AudioSegment.from_file(file_path)

        # 回退到旧的加载方式 (ID搜索)
        if audio is None:
            audio = load_tts_audio(tts_folder, clip.id, clip.text)

        if audio is None:
            logger.error(f"缺失文件: ID={clip.id}, 文本='{clip.text[:20]}...'")
            success = False
            continue

        original_duration = len(audio) / 1000.0

        # 去除首尾静音
        trimmed, saved = trim_silence(audio, silence_thresh=-40)
        clip.audio = trimmed
        clip.duration = len(trimmed) / 1000.0
        total_saved += saved

        if saved > 0.1:
            logger.debug(
                f"ID={clip.id}: {original_duration:.2f}s -> {clip.duration:.2f}s (节省 {saved:.2f}s)"
            )

    if total_saved > 0:
        logger.info(f"静音裁切共节省 {total_saved:.2f} 秒")

    return success
