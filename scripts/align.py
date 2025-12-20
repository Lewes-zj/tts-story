#!/usr/bin/env python3
"""
ABEA 核心对齐引擎 (align.py)
功能：读取对齐配置文件，执行音频排版算法，输出对齐后的音频

用法：
    python align.py [配置文件路径]

算法核心：
1. 硬锚点 (ANCHOR) - 绝对不可移动，必须与源音频时间严格对齐
2. 浮动块 (FLOATING) - 可在两个锚点之间弹性滑动
3. 连环挤压排版 + 边界回弹
"""

import os
import sys
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple

# 尝试导入 pandas，如果只用 JSON 其实可以不需要 pandas，但为了兼容性保留
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
    source_start: float  # 源音频开始时间 (秒)
    source_end: float  # 源音频结束时间 (秒)
    clip_type: str  # ANCHOR 或 FLOATING
    filename: str = ""  # TTS 文件名（新格式）
    audio: Optional[AudioSegment] = None
    duration: float = 0.0
    target_start: float = 0.0  # 计算后的目标开始时间


@dataclass
class Interval:
    """区间数据结构 - 两个锚点之间的空间"""

    left_wall: float  # 左墙 = 上一个锚点的结束时间
    right_wall: float  # 右墙 = 下一个锚点的开始时间
    clips: List[AudioClip]  # 区间内的浮动块


def trim_silence(
    audio: AudioSegment, silence_thresh: int = -40, chunk_size: int = 10
) -> Tuple[AudioSegment, float]:
    """
    去除音频首尾的静音部分
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
    """加载 TTS 音频文件"""
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


def load_config(config_path: str) -> List[AudioClip]:
    """
    加载对齐配置文件（支持 JSON 和 Excel 格式）
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
        try:
            df = pd.read_excel(config_path, engine="openpyxl")
        except NameError:
            logger.error(
                "读取Excel失败：未安装pandas或openpyxl。请运行 pip install pandas openpyxl"
            )
            sys.exit(1)

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


def load_all_tts(clips: List[AudioClip], tts_folder: str) -> bool:
    """加载所有 TTS 音频并去除静音"""
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


def build_intervals(clips: List[AudioClip]) -> List[Interval]:
    """构建区间模型 - 将时间轴划分为若干个弹簧区间"""
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

    if floating:
        first_floating_start = min(c.source_start for c in floating)
    else:
        first_floating_start = 0.0

    anchor_times = [(first_floating_start, first_floating_start)]

    for anchor in sorted(anchors, key=lambda x: x.source_start):
        anchor_times.append((anchor.source_start, anchor.source_end))

    if clips:
        last_end = max(c.source_end for c in clips)
        anchor_times.append((last_end + 30, last_end + 30))

    for i in range(len(anchor_times) - 1):
        left_wall = anchor_times[i][1]
        right_wall = anchor_times[i + 1][0]

        interval_clips = []
        for clip in clips:
            if clip.clip_type == "FLOATING":
                if left_wall <= clip.source_start < right_wall:
                    interval_clips.append(clip)

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
    """物理容量核验"""
    logger.info("执行容量核验...")
    all_ok = True

    for i, interval in enumerate(intervals):
        available_space = interval.right_wall - interval.left_wall
        required_space = sum(c.duration for c in interval.clips)

        if required_space > available_space:
            logger.error(
                f"错误：区间 {i + 1} 溢出!\n"
                f"  范围: {interval.left_wall:.3f}s ~ {interval.right_wall:.3f}s\n"
                f"  可用空间: {available_space:.3f}s\n"
                f"  需要空间: {required_space:.3f}s\n"
                f"  溢出: {required_space - available_space:.3f}s\n"
                f"  涉及片段 ID: {[c.id for c in interval.clips]}"
            )
            all_ok = False
        else:
            logger.info(
                f"区间 {i + 1}: {interval.left_wall:.3f}s ~ {interval.right_wall:.3f}s, "
                f"可用={available_space:.3f}s, 需要={required_space:.3f}s, "
                f"剩余={available_space - required_space:.3f}s"
            )

    return all_ok


def ripple_layout(intervals: List[Interval]) -> bool:
    """连环挤压排版算法"""
    logger.info("执行连环挤压排版...")

    for i, interval in enumerate(intervals):
        clips = interval.clips
        if not clips:
            continue

        cursor = interval.left_wall

        for clip in clips:
            ideal_start = clip.source_start
            if ideal_start < cursor:
                clip.target_start = cursor
            else:
                clip.target_start = ideal_start
            cursor = clip.target_start + clip.duration

        last_clip = clips[-1]
        last_end = last_clip.target_start + last_clip.duration

        if last_end > interval.right_wall:
            shift_amount = last_end - interval.right_wall
            logger.info(f"区间 {i + 1}: 撞右墙，整体左移 {shift_amount:.3f}s")

            for clip in clips:
                clip.target_start -= shift_amount

            first_clip = clips[0]
            if first_clip.target_start < interval.left_wall:
                overflow = interval.left_wall - first_clip.target_start
                logger.error(
                    f"致命错误：区间 {i + 1} 左右碰壁，死锁!\n"
                    f"  首个片段 ID={first_clip.id} 左溢出 {overflow:.3f}s\n"
                    f"  请精简文案或调整锚点位置"
                )
                return False

    return True


def place_anchors(clips: List[AudioClip]) -> None:
    """放置锚点"""
    for clip in clips:
        if clip.clip_type == "ANCHOR":
            clip.target_start = clip.source_start
            logger.info(f"锚点 ID={clip.id}: 固定在 {clip.target_start:.3f}s")


def render_output(clips: List[AudioClip], bgm_path: str, output_path: str) -> None:
    """渲染输出音频"""
    if not os.path.exists(bgm_path):
        logger.error(f"BGM 文件不存在: {bgm_path}")
        return

    logger.info(f"加载 BGM: {bgm_path}")
    bgm = AudioSegment.from_file(bgm_path)

    # 计算需要的总时长：取BGM长度和最后一个音频片段结束时间的较大值
    last_clip_end = max((c.target_start + c.duration for c in clips), default=0) * 1000
    total_duration = max(len(bgm), last_clip_end + 2000)  # 多留2秒缓冲

    # 扩展 BGM 长度（如果人声比 BGM 长）
    if total_duration > len(bgm):
        silence_padding = AudioSegment.silent(duration=total_duration - len(bgm))
        bgm = bgm + silence_padding

    voice_track = AudioSegment.silent(duration=len(bgm))

    for clip in clips:
        if clip.audio is None:
            continue

        position_ms = int(clip.target_start * 1000)

        # 防止越界
        if position_ms < 0:
            position_ms = 0

        voice_track = voice_track.overlay(clip.audio, position=position_ms)

    logger.info("混合人声与 BGM...")
    final = bgm.overlay(voice_track)

    logger.info(f"导出音频: {output_path}")
    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    final.export(output_path, format="wav")
    logger.info(f"输出文件: {output_path} ({len(final) / 1000:.1f}s)")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ABEA 核心对齐引擎")
    parser.add_argument("config", help="对齐配置文件路径 (.json 或 .xlsx)")
    parser.add_argument(
        "-t", "--tts-folder", default="tts音频积木", help="TTS 音频文件夹"
    )
    parser.add_argument("-b", "--bgm", default="BGM.mp3", help="BGM 文件路径")
    parser.add_argument(
        "-o", "--output", default="output_aligned.wav", help="输出文件路径"
    )

    args = parser.parse_args()

    if not os.path.exists(args.config):
        logger.error(f"配置文件不存在: {args.config}")
        sys.exit(1)

    if not os.path.exists(args.tts_folder):
        logger.error(f"TTS 文件夹不存在: {args.tts_folder}")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("ABEA 核心对齐引擎 (JSON/Excel 通用版)")
    logger.info("=" * 50)

    # 1. 加载配置 (支持 JSON)
    clips = load_config(args.config)

    # 2. 加载 TTS 音频
    if not load_all_tts(clips, args.tts_folder):
        logger.error("部分 TTS 文件缺失，请检查文件夹和文件名")
        sys.exit(1)

    # 3. 放置锚点
    place_anchors(clips)

    # 4. 构建区间
    intervals = build_intervals(clips)

    # 5. 容量核验
    if not capacity_check(intervals):
        logger.error("容量核验失败")
        sys.exit(1)

    # 6. 排版
    if not ripple_layout(intervals):
        logger.error("排版失败")
        sys.exit(1)

    # 7. 渲染
    render_output(clips, args.bgm, args.output)

    logger.info("完成!")


if __name__ == "__main__":
    main()
