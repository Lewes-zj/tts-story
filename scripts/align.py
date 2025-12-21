#!/usr/bin/env python3
"""
ABEA 核心对齐引擎 (align.py) - 多文件夹支持版
功能：读取对齐配置文件，在指定的多个文件夹中查找音频，执行排版算法，输出对齐后的音频

用法：
    python align.py [配置文件路径] -n [旁白文件夹] -d [对话文件夹]

算法核心：
1. 硬锚点 (ANCHOR) - 绝对不可移动
2. 浮动块 (FLOATING) - 弹性滑动
3. 连环挤压排版 + 边界回弹
"""

import os
import sys
import json
import logging
from typing import List, Optional, Tuple, Union
from dataclasses import dataclass

# 尝试导入依赖
try:
    import pandas as pd
except ImportError:
    pass

try:
    import numpy as np
    from pydub import AudioSegment
    from pydub.silence import detect_leading_silence
except ImportError:
    print("错误：请先安装 pydub 和 numpy")
    print("运行: pip install pydub numpy")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("align.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class AudioClip:
    """音频片段数据结构"""

    id: int
    text: str
    source_start: float
    source_end: float
    clip_type: str  # ANCHOR 或 FLOATING
    filename: str = ""  # TTS 文件名
    audio: Optional[AudioSegment] = None
    duration: float = 0.0
    target_start: float = 0.0


@dataclass
class Interval:
    """区间数据结构"""

    left_wall: float
    right_wall: float
    clips: List[AudioClip]


def trim_silence(
    audio: AudioSegment, silence_thresh: int = -40, chunk_size: int = 10
) -> Tuple[AudioSegment, float]:
    """去除音频首尾的静音部分"""
    original_duration = len(audio)

    def detect_silence_end(audio_segment):
        return detect_leading_silence(
            audio_segment, silence_threshold=silence_thresh, chunk_size=chunk_size
        )

    start_trim = detect_silence_end(audio)
    end_trim = detect_silence_end(audio.reverse())

    trimmed = audio[start_trim : original_duration - end_trim]

    if len(trimmed) < 100:
        return audio, 0.0

    saved_ms = original_duration - len(trimmed)
    return trimmed, saved_ms / 1000.0


def search_audio_file(search_paths: List[str], filename: str) -> Optional[AudioSegment]:
    """
    在多个文件夹中查找并加载指定文件名的音频
    """
    for folder in search_paths:
        file_path = os.path.join(folder, filename)
        if os.path.exists(file_path):
            logger.info(f"在 {folder} 中找到: {filename}")
            return AudioSegment.from_file(file_path)
    return None


def search_audio_by_pattern(
    search_paths: List[str], clip_id: int, text: str
) -> Optional[AudioSegment]:
    """
    如果文件名未知，尝试通过 ID 和文本模式在多个文件夹中搜索
    """
    patterns = [
        f"{clip_id}-{text}.wav",
        f"{clip_id}-{text}.mp3",
        f"{clip_id}_{text}.wav",
        f"{clip_id}_{text}.mp3",
        f"{clip_id}.wav",
        f"{clip_id}.mp3",
    ]

    for folder in search_paths:
        if not os.path.exists(folder):
            continue

        # 1. 精确匹配模式
        for pattern in patterns:
            path = os.path.join(folder, pattern)
            if os.path.exists(path):
                logger.info(f"匹配到文件: {path}")
                return AudioSegment.from_file(path)

        # 2. 前缀模糊匹配 (比如 10_xxx.wav)
        for f in os.listdir(folder):
            if f.startswith(f"{clip_id}-") or f.startswith(f"{clip_id}_"):
                path = os.path.join(folder, f)
                logger.info(f"模糊匹配到: {path}")
                return AudioSegment.from_file(path)

    return None


def load_config(config_path: str) -> List[AudioClip]:
    """加载配置文件 (JSON/Excel)"""
    logger.info(f"加载配置文件: {config_path}")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"文件不存在: {config_path}")

    clips = []

    # === JSON 处理 ===
    if config_path.lower().endswith(".json"):
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            clip = AudioClip(
                id=int(item.get("id")),
                text=str(item.get("text", "")).strip(),
                source_start=float(item.get("source_start", 0.0)),
                source_end=float(item.get("source_end", 0.0)),
                clip_type=str(item.get("alignment_type", "FLOATING")).upper().strip(),
                filename=str(item.get("filename", "")),
            )
            clips.append(clip)

    # === Excel 处理 ===
    elif config_path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(config_path, engine="openpyxl")
        # 替换 NaN
        data = df.where(pd.notnull(df), None).to_dict(orient="records")

        for row in data:
            # 兼容列名
            src_start = float(row.get("源开始时间(秒)") or row.get("源开始(秒)") or 0.0)
            src_end = float(row.get("源结束时间(秒)") or row.get("源结束(秒)") or 0.0)
            clip_type = (
                str(row.get("类型") or row.get("对齐类型") or "FLOATING")
                .upper()
                .strip()
            )
            text = str(row.get("文本", "")).strip()
            filename = str(row.get("文件名", ""))

            clip = AudioClip(
                id=int(row.get("ID") or row.get("id")),
                text=text,
                source_start=src_start,
                source_end=src_end,
                clip_type=clip_type,
                filename=filename,
            )
            clips.append(clip)

    else:
        raise ValueError("不支持的文件格式")

    logger.info(f"共加载 {len(clips)} 个片段")
    return clips


def load_all_tts(clips: List[AudioClip], search_paths: List[str]) -> bool:
    """
    加载所有 TTS 音频 (支持多路径搜索)
    """
    logger.info(f"将在以下路径搜索音频: {search_paths}")
    success = True
    total_saved = 0.0

    for clip in clips:
        audio = None

        # 1. 优先尝试通过文件名加载
        if clip.filename:
            audio = search_audio_file(search_paths, clip.filename)

            # 如果直接找不到，尝试只用文件名部分 (防止路径差异)
            if audio is None:
                basename = os.path.basename(clip.filename)
                audio = search_audio_file(search_paths, basename)

        # 2. 如果还没找到，尝试通过 ID 搜索
        if audio is None:
            audio = search_audio_by_pattern(search_paths, clip.id, clip.text)

        if audio is None:
            logger.error(f"❌ 缺失文件: ID={clip.id}, Filename={clip.filename}")
            success = False
            continue

        # 去除静音处理
        trimmed, saved = trim_silence(audio, silence_thresh=-40)
        clip.audio = trimmed
        clip.duration = len(trimmed) / 1000.0
        total_saved += saved

    if total_saved > 0:
        logger.info(f"静音裁切共节省 {total_saved:.2f} 秒")

    return success


def build_intervals(clips: List[AudioClip]) -> List[Interval]:
    """构建区间模型"""
    intervals = []
    anchors = [c for c in clips if c.clip_type == "ANCHOR"]
    floating = [c for c in clips if c.clip_type == "FLOATING"]

    if not anchors and floating:
        first_start = min(c.source_start for c in floating)
        last_end = max(c.source_end for c in floating)
        intervals.append(
            Interval(
                left_wall=first_start,
                right_wall=last_end + 30,
                clips=sorted(floating, key=lambda x: x.source_start),
            )
        )
        return intervals

    first_time = min(c.source_start for c in floating) if floating else 0.0
    anchor_times = [(first_time, first_time)]

    for anchor in sorted(anchors, key=lambda x: x.source_start):
        anchor_times.append((anchor.source_start, anchor.source_end))

    if clips:
        last_end = max(c.source_end for c in clips)
        anchor_times.append((last_end + 30, last_end + 30))

    for i in range(len(anchor_times) - 1):
        left_wall = anchor_times[i][1]
        right_wall = anchor_times[i + 1][0]

        interval_clips = [
            c
            for c in clips
            if c.clip_type == "FLOATING" and left_wall <= c.source_start < right_wall
        ]

        if interval_clips:
            intervals.append(
                Interval(
                    left_wall=left_wall,
                    right_wall=right_wall,
                    clips=sorted(interval_clips, key=lambda x: x.source_start),
                )
            )

    return intervals


def capacity_check(intervals: List[Interval]) -> bool:
    """容量核验"""
    all_ok = True
    for i, interval in enumerate(intervals):
        available = interval.right_wall - interval.left_wall
        required = sum(c.duration for c in interval.clips)
        if required > available:
            logger.error(
                f"区间 {i + 1} 溢出: 需要 {required:.2f}s, 可用 {available:.2f}s"
            )
            all_ok = False
    return all_ok


def ripple_layout(intervals: List[Interval]) -> bool:
    """排版算法"""
    for i, interval in enumerate(intervals):
        if not interval.clips:
            continue

        cursor = interval.left_wall
        for clip in interval.clips:
            clip.target_start = max(cursor, clip.source_start)
            cursor = clip.target_start + clip.duration

        # 边界回弹
        last_end = interval.clips[-1].target_start + interval.clips[-1].duration
        if last_end > interval.right_wall:
            shift = last_end - interval.right_wall
            for clip in interval.clips:
                clip.target_start -= shift

            if interval.clips[0].target_start < interval.left_wall:
                logger.error(f"区间 {i + 1} 严重溢出 (死锁)")
                return False
    return True


def place_anchors(clips: List[AudioClip]) -> None:
    for clip in clips:
        if clip.clip_type == "ANCHOR":
            clip.target_start = clip.source_start


def render_output(clips: List[AudioClip], bgm_path: str, output_path: str) -> None:
    """渲染输出"""
    logger.info(f"导出目标: {output_path}")

    # 准备 BGM
    bgm = None
    if bgm_path and os.path.exists(bgm_path):
        logger.info(f"加载 BGM: {bgm_path}")
        bgm = AudioSegment.from_file(bgm_path)
    else:
        logger.warning("未找到 BGM，将生成纯人声")

    # 计算总时长
    last_end = max((c.target_start + c.duration for c in clips), default=0) * 1000
    total_dur = last_end + 2000
    if bgm:
        total_dur = max(len(bgm), total_dur)

    # 画布
    if bgm:
        if len(bgm) < total_dur:
            bgm += AudioSegment.silent(duration=total_dur - len(bgm))
        final = bgm
    else:
        final = AudioSegment.silent(duration=total_dur)

    voice_track = AudioSegment.silent(duration=total_dur)

    for clip in clips:
        if clip.audio:
            pos = int(clip.target_start * 1000)
            voice_track = voice_track.overlay(clip.audio, position=max(0, pos))

    if bgm:
        final = final.overlay(voice_track)
    else:
        final = voice_track

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    final.export(output_path, format="wav")
    logger.info(f"✅ 输出成功: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ABEA 核心对齐引擎 (多文件夹版)")
    parser.add_argument("config", help="配置文件路径")

    # 支持多个文件夹参数
    parser.add_argument("-n", "--narrator", help="旁白音频文件夹")
    parser.add_argument("-d", "--dialogue", help="对话音频文件夹")
    parser.add_argument("-t", "--tts-folder", help="TTS 音频文件夹 (兼容旧版)")

    parser.add_argument("-b", "--bgm", default="", help="BGM 文件路径")
    parser.add_argument(
        "-o", "--output", default="output_aligned.wav", help="输出文件路径"
    )

    args = parser.parse_args()

    # 1. 构建搜索路径列表
    search_paths = []
    if args.narrator:
        search_paths.append(args.narrator)
    if args.dialogue:
        search_paths.append(args.dialogue)
    if args.tts_folder:
        search_paths.append(args.tts_folder)

    if not search_paths:
        logger.error("❌ 错误: 必须至少提供一个音频文件夹 (-n, -d 或 -t)")
        sys.exit(1)

    # 2. 运行流程
    clips = load_config(args.config)

    if not load_all_tts(clips, search_paths):
        logger.error("❌ 音频加载失败，终止程序")
        sys.exit(1)

    place_anchors(clips)
    intervals = build_intervals(clips)

    if not capacity_check(intervals):
        sys.exit(1)

    if not ripple_layout(intervals):
        sys.exit(1)

    render_output(clips, args.bgm, args.output)


if __name__ == "__main__":
    main()
