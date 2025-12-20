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
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    import pandas as pd
except ImportError:
    print("错误：请先安装 pandas")
    print("运行: pip install pandas openpyxl")
    sys.exit(1)

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
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class AudioClip:
    """音频片段数据结构"""
    id: int
    text: str
    source_start: float  # 源音频开始时间 (秒)
    source_end: float    # 源音频结束时间 (秒)
    clip_type: str       # ANCHOR 或 FLOATING
    filename: str = ""   # TTS 文件名（新格式）
    audio: Optional[AudioSegment] = None
    duration: float = 0.0
    target_start: float = 0.0  # 计算后的目标开始时间


@dataclass
class Interval:
    """区间数据结构 - 两个锚点之间的空间"""
    left_wall: float      # 左墙 = 上一个锚点的结束时间
    right_wall: float     # 右墙 = 下一个锚点的开始时间
    clips: List[AudioClip]  # 区间内的浮动块


def trim_silence(audio: AudioSegment, silence_thresh: int = -40, chunk_size: int = 10) -> Tuple[AudioSegment, float]:
    """
    去除音频首尾的静音部分

    参数:
        silence_thresh: 静音阈值 (dB)，默认 -40dB，值越大裁切越激进
        chunk_size: 检测块大小 (ms)

    返回:
        (裁切后的音频, 节省的时长秒数)
    """
    original_duration = len(audio)

    def detect_silence_end(audio_segment):
        return detect_leading_silence(audio_segment, silence_threshold=silence_thresh, chunk_size=chunk_size)

    start_trim = detect_silence_end(audio)
    end_trim = detect_silence_end(audio.reverse())

    trimmed = audio[start_trim:original_duration - end_trim]

    # 确保不会返回空音频
    if len(trimmed) < 100:  # 至少保留 100ms
        return audio, 0.0

    saved_ms = original_duration - len(trimmed)
    return trimmed, saved_ms / 1000.0


def load_tts_audio(tts_folder: str, clip_id: int, text: str) -> Optional[AudioSegment]:
    """加载 TTS 音频文件"""
    # 尝试多种文件名格式
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

    # 尝试匹配以 ID 开头的文件
    for file in os.listdir(tts_folder):
        if file.startswith(f"{clip_id}-"):
            file_path = os.path.join(tts_folder, file)
            logger.info(f"加载 TTS 文件: {file}")
            return AudioSegment.from_file(file_path)

    return None


def load_config(config_path: str) -> List[AudioClip]:
    """加载对齐配置文件（支持两种格式）"""
    logger.info(f"加载配置文件: {config_path}")

    df = pd.read_excel(config_path, engine="openpyxl")

    clips = []
    for _, row in df.iterrows():
        # 兼容两种配置格式
        if "源开始时间(秒)" in df.columns:
            # 旧格式
            src_start = float(row["源开始时间(秒)"])
            src_end = float(row["源结束时间(秒)"])
            clip_type = str(row["类型"]).upper().strip()
            text = str(row["文本"]).strip()
        else:
            # 新格式 (init_full.py 生成)
            src_start = float(row["源开始(秒)"])
            src_end = float(row["源结束(秒)"])
            clip_type = str(row["对齐类型"]).upper().strip()
            text = str(row["文本"]).strip()

        # 获取文件名（新格式有，旧格式没有）
        filename = str(row.get("文件名", "")) if "文件名" in df.columns else ""

        clip = AudioClip(
            id=int(row["ID"]),
            text=text,
            source_start=src_start,
            source_end=src_end,
            clip_type=clip_type,
            filename=filename
        )
        clips.append(clip)

    logger.info(f"共加载 {len(clips)} 个片段")

    # 统计锚点和浮动块数量
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

        # 优先使用文件名直接加载（新格式）
        if clip.filename:
            file_path = os.path.join(tts_folder, clip.filename)
            if os.path.exists(file_path):
                logger.info(f"加载: {clip.filename}")
                audio = AudioSegment.from_file(file_path)

        # 回退到旧的加载方式
        if audio is None:
            audio = load_tts_audio(tts_folder, clip.id, clip.text)

        if audio is None:
            logger.error(f"缺失文件: ID={clip.id}, 文本='{clip.text[:20]}...'")
            success = False
            continue

        original_duration = len(audio) / 1000.0

        # 去除首尾静音 (使用更激进的阈值 -40dB)
        trimmed, saved = trim_silence(audio, silence_thresh=-40)
        clip.audio = trimmed
        clip.duration = len(trimmed) / 1000.0  # 转换为秒
        total_saved += saved

        if saved > 0.1:  # 只记录节省超过 0.1 秒的
            logger.debug(f"ID={clip.id}: {original_duration:.2f}s -> {clip.duration:.2f}s (节省 {saved:.2f}s)")

    if total_saved > 0:
        logger.info(f"静音裁切共节省 {total_saved:.2f} 秒")

    return success


def build_intervals(clips: List[AudioClip]) -> List[Interval]:
    """构建区间模型 - 将时间轴划分为若干个弹簧区间"""
    intervals = []

    # 找出所有锚点和浮动块
    anchors = [c for c in clips if c.clip_type == "ANCHOR"]
    floating = [c for c in clips if c.clip_type == "FLOATING"]

    # 如果没有锚点，使用第一个片段的开始时间作为起点
    if not anchors and floating:
        first_start = min(c.source_start for c in floating)
        last_end = max(c.source_end for c in floating)
        # 创建一个大区间，左墙为第一个片段的开始时间
        intervals.append(Interval(
            left_wall=first_start,
            right_wall=last_end + 30,  # 结尾缓冲 30 秒
            clips=sorted(floating, key=lambda x: x.source_start)
        ))
        return intervals

    # 有锚点的情况：添加虚拟的起始锚点
    if floating:
        first_floating_start = min(c.source_start for c in floating)
    else:
        first_floating_start = 0.0

    anchor_times = [(first_floating_start, first_floating_start)]  # 起始边界

    for anchor in sorted(anchors, key=lambda x: x.source_start):
        anchor_times.append((anchor.source_start, anchor.source_end))

    # 添加虚拟的结束锚点
    if clips:
        last_end = max(c.source_end for c in clips)
        anchor_times.append((last_end + 30, last_end + 30))

    # 构建每个区间
    for i in range(len(anchor_times) - 1):
        left_wall = anchor_times[i][1]   # 上一个锚点的结束时间
        right_wall = anchor_times[i + 1][0]  # 下一个锚点的开始时间

        # 找出在这个区间内的浮动块
        interval_clips = []
        for clip in clips:
            if clip.clip_type == "FLOATING":
                # 判断片段是否属于这个区间 (按源音频开始时间)
                if left_wall <= clip.source_start < right_wall:
                    interval_clips.append(clip)

        if interval_clips:
            intervals.append(Interval(
                left_wall=left_wall,
                right_wall=right_wall,
                clips=sorted(interval_clips, key=lambda x: x.source_start)
            ))

    return intervals


def capacity_check(intervals: List[Interval]) -> bool:
    """物理容量核验 - 检查每个区间是否能容纳所有 TTS 内容"""
    logger.info("执行容量核验...")
    all_ok = True

    for i, interval in enumerate(intervals):
        available_space = interval.right_wall - interval.left_wall
        required_space = sum(c.duration for c in interval.clips)

        if required_space > available_space:
            logger.error(
                f"错误：区间 {i+1} 溢出!\n"
                f"  范围: {interval.left_wall:.3f}s ~ {interval.right_wall:.3f}s\n"
                f"  可用空间: {available_space:.3f}s\n"
                f"  需要空间: {required_space:.3f}s\n"
                f"  溢出: {required_space - available_space:.3f}s\n"
                f"  涉及片段 ID: {[c.id for c in interval.clips]}"
            )
            all_ok = False
        else:
            logger.info(
                f"区间 {i+1}: {interval.left_wall:.3f}s ~ {interval.right_wall:.3f}s, "
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

        # Step 1: 初始对齐 - 先尝试放在原本位置
        cursor = interval.left_wall

        for clip in clips:
            # 理想开始位置是源音频的开始时间
            ideal_start = clip.source_start

            if ideal_start < cursor:
                # 被迫推迟 - 紧贴在前一个片段后面
                clip.target_start = cursor
            else:
                # 正常对齐
                clip.target_start = ideal_start

            # 移动游标到当前片段结束位置
            cursor = clip.target_start + clip.duration

        # Step 2: 撞墙检查与回弹
        last_clip = clips[-1]
        last_end = last_clip.target_start + last_clip.duration

        if last_end > interval.right_wall:
            # 撞到右墙了，整体左移
            shift_amount = last_end - interval.right_wall
            logger.info(f"区间 {i+1}: 撞右墙，整体左移 {shift_amount:.3f}s")

            for clip in clips:
                clip.target_start -= shift_amount

            # 检查是否撞左墙
            first_clip = clips[0]
            if first_clip.target_start < interval.left_wall:
                overflow = interval.left_wall - first_clip.target_start
                logger.error(
                    f"致命错误：区间 {i+1} 左右碰壁，死锁!\n"
                    f"  首个片段 ID={first_clip.id} 左溢出 {overflow:.3f}s\n"
                    f"  请精简文案或调整锚点位置"
                )
                return False

    return True


def place_anchors(clips: List[AudioClip]) -> None:
    """放置锚点 - 锚点的目标时间就是源音频时间"""
    for clip in clips:
        if clip.clip_type == "ANCHOR":
            clip.target_start = clip.source_start
            logger.info(f"锚点 ID={clip.id}: 固定在 {clip.target_start:.3f}s")


def render_output(clips: List[AudioClip], bgm_path: str, output_path: str) -> None:
    """渲染输出音频 - 将所有片段混合到 BGM 上"""
    logger.info(f"加载 BGM: {bgm_path}")
    bgm = AudioSegment.from_file(bgm_path)

    # 创建一个与 BGM 等长的空白音轨
    voice_track = AudioSegment.silent(duration=len(bgm))

    # 将每个片段叠加到对应位置
    for clip in clips:
        if clip.audio is None:
            logger.warning(f"跳过无音频的片段: ID={clip.id}")
            continue

        position_ms = int(clip.target_start * 1000)

        # 确保不超出音轨长度
        if position_ms + len(clip.audio) > len(voice_track):
            logger.warning(
                f"片段 ID={clip.id} 超出音轨长度，将被截断 "
                f"(位置={position_ms}ms, 时长={len(clip.audio)}ms, 总长={len(voice_track)}ms)"
            )

        voice_track = voice_track.overlay(clip.audio, position=position_ms)
        logger.debug(f"放置 ID={clip.id} 在 {clip.target_start:.3f}s")

    # 混合人声和 BGM
    logger.info("混合人声与 BGM...")
    final = bgm.overlay(voice_track)

    # 导出
    logger.info(f"导出音频: {output_path}")
    final.export(output_path, format="wav")
    logger.info(f"输出文件: {output_path} ({len(final)/1000:.1f}s)")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="ABEA 核心对齐引擎 - 执行音频排版算法"
    )
    parser.add_argument(
        "config",
        nargs="?",
        default="alignment_config.xlsx",
        help="对齐配置文件路径 (默认: alignment_config.xlsx)"
    )
    parser.add_argument(
        "-t", "--tts-folder",
        default="tts音频积木",
        help="TTS 音频文件夹 (默认: tts音频积木)"
    )
    parser.add_argument(
        "-b", "--bgm",
        default="BGM.mp3",
        help="BGM 文件路径 (默认: BGM.mp3)"
    )
    parser.add_argument(
        "-o", "--output",
        default="output_aligned.wav",
        help="输出文件路径 (默认: output_aligned.wav)"
    )

    args = parser.parse_args()

    # 检查文件是否存在
    if not os.path.exists(args.config):
        logger.error(f"配置文件不存在: {args.config}")
        logger.error("请先运行 init.py 生成配置文件，并完成人工标注")
        sys.exit(1)

    if not os.path.exists(args.tts_folder):
        logger.error(f"TTS 文件夹不存在: {args.tts_folder}")
        sys.exit(1)

    if not os.path.exists(args.bgm):
        logger.error(f"BGM 文件不存在: {args.bgm}")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("ABEA 核心对齐引擎")
    logger.info("=" * 50)

    # Step 1: 加载配置
    clips = load_config(args.config)

    # Step 2: 加载 TTS 音频
    if not load_all_tts(clips, args.tts_folder):
        logger.error("部分 TTS 文件缺失，请检查文件名是否匹配")
        sys.exit(1)

    # Step 3: 放置锚点
    place_anchors(clips)

    # Step 4: 构建区间模型
    intervals = build_intervals(clips)
    logger.info(f"共构建 {len(intervals)} 个排版区间")

    # Step 5: 容量核验
    if not capacity_check(intervals):
        logger.error("容量核验失败！请精简文案或调整锚点")
        sys.exit(1)

    # Step 6: 连环挤压排版
    if not ripple_layout(intervals):
        logger.error("排版失败！存在无法解决的冲突")
        sys.exit(1)

    # Step 7: 渲染输出
    render_output(clips, args.bgm, args.output)

    logger.info("=" * 50)
    logger.info("对齐完成!")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
