#!/usr/bin/env python3
"""
ABEA 项目初始化脚本 (generate_time_map.py) - JSON版
功能：扫描 TTS 文件夹，使用 Whisper ASR 获取真实时间戳，通过文本匹配生成对齐配置文件

用法：
    python generate_time_map.py [源音频路径]
    python generate_time_map.py -t tts音频积木 纯人声.mp3

核心逻辑：
1. 扫描 TTS 文件夹，获取所有音频片段
2. 使用 Whisper ASR 转录源音频，获取真实时间戳
3. 通过文本相似度匹配，为每个 TTS 找到对应的源音频时间
"""

import os
import sys
import re
import argparse
import json
from difflib import SequenceMatcher

try:
    import whisper
except ImportError:
    print("错误：请先安装 openai-whisper")
    print("运行: pip install openai-whisper")
    sys.exit(1)

# 简繁转换映射表（常用字）
TRAD_TO_SIMP = str.maketrans(
    "個們這裡來時後說東車開門書長間點過頭話問題實現發認為從無還進動種對應關電視機場愛業務員會議論語學習題號碼頭條約書記錄製導師範圍繞線圖書館員警車間題號碼頭條約書記錄製導師範圍繞線圖書館員連續劇場邊緣",
    "个们这里来时后说东车开门书长间点过头话问题实现发认为从无还进动种对应关电视机场爱业务员会议论语学习题号码头条约书记录制导师范围绕线图书馆员警车间题号码头条约书记录制导师范围绕线图书馆员连续剧场边缘",
)


def to_simplified(text: str) -> str:
    """繁体转简体（简易版）"""
    return text.translate(TRAD_TO_SIMP)


def normalize_text(text: str) -> str:
    """标准化文本用于比较"""
    # 移除标点、空格，转小写，繁转简
    text = to_simplified(text)
    text = re.sub(r"[^\w]", "", text)
    return text.lower()


def text_similarity(text1: str, text2: str) -> float:
    """计算两段文本的相似度"""
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    return SequenceMatcher(None, norm1, norm2).ratio()


def scan_tts_folder(folder_path: str) -> list:
    """扫描 TTS 文件夹，提取文件信息"""
    tts_files = []

    for filename in os.listdir(folder_path):
        if not filename.lower().endswith((".wav", ".mp3", ".flac", ".m4a")):
            continue

        # 解析文件名：格式为 "ID-文本内容.wav" or "ID_文本内容.wav"
        match = re.match(
            r"^(\d+)[-_](.+)\.(wav|mp3|flac|m4a)$", filename, re.IGNORECASE
        )
        if match:
            file_id = int(match.group(1))
            text = match.group(2)
        else:
            continue

        tts_files.append(
            {
                "id": file_id,
                "text": text,
                "filename": filename,
            }
        )

    # 按 ID 排序
    tts_files.sort(key=lambda x: x["id"])
    return tts_files


def transcribe_audio(audio_path: str, model_name: str = "medium") -> dict:
    """使用 Whisper 转录音频并获取时间戳"""
    print(f"正在加载 Whisper 模型 ({model_name})...")
    model = whisper.load_model(model_name)

    print(f"正在转录音频: {audio_path}")
    result = model.transcribe(
        audio_path, language="zh", word_timestamps=True, verbose=False
    )

    return result


def match_tts_to_whisper(tts_files: list, whisper_segments: list) -> list:
    """
    将 TTS 文件与 Whisper 段落匹配，获取真实时间戳
    """
    results = []
    whisper_idx = 0
    total_whisper = len(whisper_segments)

    for tts in tts_files:
        tts_text = tts["text"]
        best_start = None
        best_end = None
        matched_segments = []

        # 从当前位置开始搜索匹配的 Whisper 段落
        search_start = max(0, whisper_idx - 2)  # 允许少量回溯
        search_end = min(total_whisper, whisper_idx + 10)  # 向前搜索范围

        best_score = 0

        # 尝试找到最佳匹配的起始位置
        for start_idx in range(search_start, search_end):
            # 尝试合并连续的 Whisper 段落来匹配 TTS
            combined_text = ""
            for end_idx in range(start_idx, min(start_idx + 5, total_whisper)):
                combined_text += whisper_segments[end_idx]["text"]
                score = text_similarity(tts_text, combined_text)

                if score > best_score:
                    best_score = score
                    best_start = whisper_segments[start_idx]["start"]
                    best_end = whisper_segments[end_idx]["end"]
                    matched_segments = list(range(start_idx, end_idx + 1))

                # 如果相似度很高，停止搜索
                if score > 0.8:
                    break

        # 更新 Whisper 索引位置
        if matched_segments:
            whisper_idx = matched_segments[-1] + 1

        # 如果没有找到好的匹配，使用估算
        if best_start is None or best_score < 0.3:
            print(
                f"  警告: ID={tts['id']} 匹配度低 ({best_score:.2f}): {tts_text[:30]}..."
            )
            if whisper_idx < total_whisper:
                best_start = whisper_segments[whisper_idx]["start"]
                best_end = whisper_segments[whisper_idx]["end"]
                whisper_idx += 1

        results.append(
            {
                "id": tts["id"],
                "text": tts["text"],
                "filename": tts["filename"],
                "source_start": round(best_start, 3) if best_start else 0,
                "source_end": round(best_end, 3) if best_end else 0,
                "match_score": round(best_score, 2),
            }
        )

        print(
            f"  ID={tts['id']:2d}: {best_start:6.1f}s ~ {best_end:6.1f}s (匹配度:{best_score:.2f}) {tts_text[:25]}..."
        )

    return results


def create_alignment_config(matched_results: list, output_path: str) -> None:
    """创建对齐配置 JSON 文件"""
    data = []
    for item in matched_results:
        data.append(
            {
                "id": item["id"],
                "text": item["text"],
                "source_start": item["source_start"],
                "source_end": item["source_end"],
                "duration": round(item["source_end"] - item["source_start"], 3),
                "type": "FLOATING",
                "match_score": item["match_score"],
                "note": "",
            }
        )

    # 输出为 JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"\n配置文件已生成: {output_path}")
    print(f"共 {len(data)} 个 TTS 片段")

    # 统计匹配质量
    high_match = sum(1 for d in data if d["match_score"] >= 0.6)
    low_match = sum(1 for d in data if d["match_score"] < 0.4)
    print(f"匹配质量: 高({high_match}), 低({low_match})")


def find_default_audio() -> str:
    """查找默认的音频文件"""
    candidates = ["纯人声.mp3", "源音频.mp3"]
    for name in candidates:
        if os.path.exists(name):
            return name
    return None


def main():
    parser = argparse.ArgumentParser(
        description="ABEA 项目初始化 - 使用 Whisper ASR 生成对齐配置文件 (JSON版)"
    )
    parser.add_argument(
        "audio", nargs="?", help="源音频文件路径 (默认: 纯人声.mp3 或 源音频.mp3)"
    )
    parser.add_argument(
        "-t",
        "--tts-folder",
        default="tts音频积木",
        help="TTS 音频文件夹路径 (默认: tts音频积木)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="alignment_config.json",
        help="输出 JSON 文件路径 (默认: alignment_config.json)",
    )
    parser.add_argument(
        "-m",
        "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper 模型大小 (默认: medium)",
    )

    args = parser.parse_args()

    # 检查 TTS 文件夹
    if not os.path.exists(args.tts_folder):
        print(f"错误：TTS 文件夹不存在: {args.tts_folder}")
        sys.exit(1)

    # 确定音频文件路径
    audio_path = args.audio
    if not audio_path:
        audio_path = find_default_audio()
        if not audio_path:
            print("错误：未找到音频文件")
            sys.exit(1)

    if not os.path.exists(audio_path):
        print(f"错误：文件不存在: {audio_path}")
        sys.exit(1)

    print("=" * 50)
    print("ABEA 项目初始化 (真实时间戳 JSON版)")
    print("=" * 50)
    print(f"TTS 文件夹: {args.tts_folder}")
    print(f"源音频文件: {audio_path}")
    print(f"输出文件: {args.output}")
    print("=" * 50)

    # Step 1: 扫描 TTS 文件夹
    print("\n[1/3] 扫描 TTS 文件夹...")
    tts_files = scan_tts_folder(args.tts_folder)
    print(f"找到 {len(tts_files)} 个 TTS 文件")

    if not tts_files:
        print("错误：未找到有效的 TTS 文件")
        sys.exit(1)

    # Step 2: 转录源音频
    print("\n[2/3] 转录源音频...")
    transcription = transcribe_audio(audio_path, args.model)
    whisper_segments = transcription.get("segments", [])
    print(f"Whisper 识别出 {len(whisper_segments)} 个段落")
    print(f"源音频时长: {whisper_segments[-1]['end']:.1f} 秒")

    # Step 3: 匹配时间戳
    print("\n[3/3] 匹配 TTS 与源音频时间戳...")
    matched_results = match_tts_to_whisper(tts_files, whisper_segments)

    # 生成配置文件
    create_alignment_config(matched_results, args.output)

    print("\n" + "=" * 50)
    print("初始化完成!")
    print("=" * 50)
    print("\n请检查生成的 JSON 文件是否正确。")


if __name__ == "__main__":
    main()
