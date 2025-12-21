#!/usr/bin/env python3
"""
ABEA 核心对齐引擎 (align.py) - 纯粹绝对对齐版
逻辑：
1. 信任 JSON 中的 source_start 时间点。
2. 信任 TTS 音频的自然时长（仅去除首尾静音）。
3. 绝对不进行变速、压缩操作。
"""

import os
import sys
import json
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

try:
    import numpy as np
    from pydub import AudioSegment
    from pydub.silence import detect_leading_silence
except ImportError:
    print("错误：请先安装 pydub 和 numpy")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@dataclass
class AudioClip:
    id: int
    text: str
    source_start: float  # 源音频开始时间 (绝对锚点)
    source_end: float
    filename: str = ""
    audio: Optional[AudioSegment] = None
    target_start: float = 0.0


def trim_silence(
    audio: AudioSegment, silence_thresh: int = -40, chunk_size: int = 10
) -> AudioSegment:
    """去除首尾静音"""
    if len(audio) == 0:
        return audio

    def detect_silence_end(audio_segment):
        return detect_leading_silence(
            audio_segment, silence_threshold=silence_thresh, chunk_size=chunk_size
        )

    start_trim = detect_silence_end(audio)
    end_trim = detect_silence_end(audio.reverse())

    if start_trim + end_trim >= len(audio):
        return audio  # 全是静音，就不切了，或者返回空

    return audio[start_trim : len(audio) - end_trim]


def search_audio_file(search_paths: List[str], filename: str) -> Optional[AudioSegment]:
    for folder in search_paths:
        file_path = os.path.join(folder, filename)
        if os.path.exists(file_path):
            return AudioSegment.from_file(file_path)
    return None


def search_audio_by_pattern(
    search_paths: List[str], clip_id: int, text: str
) -> Optional[AudioSegment]:
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
        for pattern in patterns:
            path = os.path.join(folder, pattern)
            if os.path.exists(path):
                return AudioSegment.from_file(path)
        for f in os.listdir(folder):
            if f.startswith(f"{clip_id}-") or f.startswith(f"{clip_id}_"):
                path = os.path.join(folder, f)
                return AudioSegment.from_file(path)
    return None


def load_config(config_path: str) -> List[AudioClip]:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"文件不存在: {config_path}")
    clips = []

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        # 读取精准的 source_start
        src_start = float(item.get("source_start", 0.0))
        src_end = float(item.get("source_end", 0.0))

        clip = AudioClip(
            id=int(item.get("id")),
            text=str(item.get("text", "")).strip(),
            source_start=src_start,
            source_end=src_end,
            filename=str(item.get("filename", "")),
        )
        clips.append(clip)

    clips.sort(key=lambda x: x.id)
    return clips


def load_and_prep_audio(clips: List[AudioClip], search_paths: List[str]) -> bool:
    """加载音频并做静音处理"""
    logger.info(f"在以下路径搜索音频: {search_paths}")
    success = True

    for clip in clips:
        audio = None
        # 1. 文件名搜索
        if clip.filename:
            audio = search_audio_file(search_paths, clip.filename)
            if audio is None:
                audio = search_audio_file(search_paths, os.path.basename(clip.filename))

        # 2. 模糊搜索
        if audio is None:
            audio = search_audio_by_pattern(search_paths, clip.id, clip.text)

        if audio is None:
            logger.error(f"❌ 缺失文件: ID={clip.id} {clip.text[:10]}")
            success = False
            continue

        # 3. 去除静音 (这是唯一允许的音频处理)
        clip.audio = trim_silence(audio, silence_thresh=-40)

        # 4. 绝对定位：目标时间就是源时间
        clip.target_start = clip.source_start

    return success


def render_output(clips: List[AudioClip], bgm_path: str, output_path: str) -> None:
    logger.info(f"导出目标: {output_path}")

    # 1. 准备 BGM
    if not os.path.exists(bgm_path):
        logger.error("❌ 必须提供 BGM 文件路径")
        sys.exit(1)

    bgm = AudioSegment.from_file(bgm_path)

    # 2. 计算画布总长度
    # 我们以 BGM 长度为基准，如果人声最后超出了，就延展 BGM
    last_voice_end = max(
        (c.target_start * 1000 + len(c.audio)) for c in clips if c.audio
    )
    total_dur = max(len(bgm), last_voice_end + 1000)

    if len(bgm) < total_dur:
        bgm += AudioSegment.silent(duration=total_dur - len(bgm))

    final = bgm  # 直接在 BGM 上操作

    # 3. 叠加人声 (Overlay)
    voice_track = AudioSegment.silent(duration=total_dur)

    overlap_log = []

    for i, clip in enumerate(clips):
        if clip.audio is None:
            continue

        pos = int(clip.target_start * 1000)

        # 检测重叠 (仅用于日志提醒，不改变行为)
        if i > 0:
            prev = clips[i - 1]
            if prev.audio:
                prev_end = int(prev.target_start * 1000) + len(prev.audio)
                if prev_end > pos:
                    overlap_ms = prev_end - pos
                    overlap_log.append(f"ID {prev.id} 与 {clip.id} 重叠 {overlap_ms}ms")

        voice_track = voice_track.overlay(clip.audio, position=max(0, pos))

    if overlap_log:
        logger.warning(f"⚠️  检测到 {len(overlap_log)} 处音频重叠 (已自然混合):")
        for log in overlap_log[:5]:
            logger.warning(f"  - {log}")
        if len(overlap_log) > 5:
            logger.warning("  - ...")

    # 4. 最终混音
    final = final.overlay(voice_track)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    final.export(output_path, format="wav")
    logger.info(f"✅ 输出成功: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ABEA 核心对齐引擎 (绝对时间轴版)")
    parser.add_argument("config", help="配置文件路径")
    parser.add_argument("-n", "--narrator", help="旁白音频文件夹")
    parser.add_argument("-d", "--dialogue", help="对话音频文件夹")
    parser.add_argument("-t", "--tts-folder", help="单一TTS文件夹")
    parser.add_argument("-b", "--bgm", required=True, help="BGM源音频路径")
    parser.add_argument(
        "-o", "--output", default="output_aligned.wav", help="输出文件路径"
    )

    args = parser.parse_args()

    search_paths = []
    if args.narrator:
        search_paths.append(args.narrator)
    if args.dialogue:
        search_paths.append(args.dialogue)
    if args.tts_folder:
        search_paths.append(args.tts_folder)

    if not search_paths:
        logger.error("❌ 错误: 请提供音频文件夹")
        sys.exit(1)

    clips = load_config(args.config)

    if not load_and_prep_audio(clips, search_paths):
        sys.exit(1)

    render_output(clips, args.bgm, args.output)


if __name__ == "__main__":
    main()
