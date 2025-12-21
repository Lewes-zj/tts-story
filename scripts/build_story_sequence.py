#!/usr/bin/env python3
"""
ABEA 完整初始化脚本 (build_story_sequence.py) - V5.1 通用架构版
修改点：
1. 彻底移除硬编码的角色判断逻辑 (不再写死 HS=华生)。
2. 完全信任 script.json 中的 role 字段。
3. 即使文件名里没有角色信息，只要 ID 对得上，就能正确关联。
"""

import os
import sys
import re
import json
import argparse
from difflib import SequenceMatcher

# 强制禁用 Triton
sys.modules["triton"] = None

try:
    import whisper
    from pydub import AudioSegment
except ImportError:
    print("错误：请安装依赖 - pip install openai-whisper pydub")
    sys.exit(1)


def get_duration(path):
    try:
        return len(AudioSegment.from_file(path)) / 1000.0
    except:
        return 0.0


def normalize(text):
    """文本标准化：转小写，去标点"""
    return re.sub(r"[^\w]", "", text).lower()


# =======================================================
# 1. 数据加载模块 (通用化)
# =======================================================


def load_script_file(json_path):
    """读取用户提供的完整台词脚本"""
    if not json_path or not os.path.exists(json_path):
        print(f"❌ 脚本文件不存在: {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 转为字典映射： id -> info
    script_map = {}
    for item in data:
        uid = item.get("id") or item.get("sort")
        if uid is not None:
            script_map[int(uid)] = {
                "text": item.get("text", ""),
                "role": item.get("role", "未知角色"),  # 默认值，不猜
            }

    print(f"✅ 已加载脚本数据: {len(script_map)} 条")
    return script_map


def scan_audio_directories(folders):
    """
    通用扫描：只负责提取 ID 和 文件路径
    不再尝试从文件名猜测角色
    """
    audio_map = {}

    for path in folders:
        if not os.path.exists(path):
            print(f"⚠️ 警告: 文件夹不存在 {path}")
            continue

        for f in os.listdir(path):
            if not f.lower().endswith((".wav", ".mp3", ".flac")):
                continue

            # 核心逻辑：只认 ID (数字开头)
            # 匹配 "21-xxx.wav" 或 "21_xxx.wav"
            m = re.match(r"^(\d+)[-_]", f)
            if m:
                uid = int(m.group(1))
                full_path = os.path.join(path, f)

                audio_map[uid] = {
                    "file": f,
                    "path": full_path,
                    "duration": get_duration(full_path),
                }

    print(f"✅ 已扫描音频文件: {len(audio_map)} 个")
    return audio_map


def merge_data(script_map, audio_map):
    """
    将脚本数据(灵魂)注入到音频数据(肉体)中
    """
    sequence = []

    # 以音频文件为基准（因为必须有声音才能对齐）
    all_ids = sorted(audio_map.keys())

    for uid in all_ids:
        audio_info = audio_map[uid]
        script_info = script_map.get(uid)

        # 默认值
        final_text = ""
        final_role = "未知"

        if script_info:
            # 情况A: 脚本里有配置 -> 完美，直接用
            final_text = script_info["text"]
            final_role = script_info["role"]
        else:
            # 情况B: 脚本里漏写了这句 -> 尝试从文件名提取一点信息做兜底
            print(f"⚠️ ID {uid} 在脚本json中未找到，将使用文件名作为文本")
            m = re.match(r"^\d+[-_](.+)\.", audio_info["file"])
            final_text = m.group(1) if m else "未知文本"
            final_role = "未定义"

        sequence.append(
            {
                "seq_id": uid,
                "role": final_role,  # 直接使用 JSON 里的角色
                "text": final_text,  # 直接使用 JSON 里的长文本
                "file": audio_info["file"],
                "path": audio_info["path"],
                "tts_dur": audio_info["duration"],
                "src_start": 0.0,
                "src_end": 0.0,
                "match": 0.0,
            }
        )

    return sequence


# =======================================================
# 2. Whisper 匹配与填缝模块 (保持 V4.0 逻辑不变)
# =======================================================


def match_whisper_v3(audio_path, sequence, model="medium"):
    print(f"\n[1/2] Whisper 识别中 ({model})...")
    m = whisper.load_model(model)
    res = m.transcribe(audio_path, language="zh", word_timestamps=True, verbose=False)

    all_words = []
    for s in res["segments"]:
        for w in s["words"]:
            all_words.append(
                {"word": normalize(w["word"]), "start": w["start"], "end": w["end"]}
            )

    cursor = 0
    last_end = 0.0

    for item in sequence:
        target = normalize(item["text"])
        # 搜索范围加大，适应长文本
        search_limit = min(len(all_words), cursor + 300)

        best_s, best_e, best_score = None, None, 0
        new_cursor = cursor

        for i in range(cursor, search_limit):
            phrase = ""
            for j in range(i, min(len(all_words), i + 60)):
                phrase += all_words[j]["word"]
                sim = SequenceMatcher(None, target, phrase).ratio()
                if sim > best_score:
                    best_score = sim
                    best_s = all_words[i]["start"]
                    best_e = all_words[j]["end"]
                    new_cursor = j + 1
                    if sim > 0.85:
                        break
            if best_score > 0.85:
                break

        valid = False
        if best_s is not None:
            if best_score > 0.35 and best_s >= last_end - 0.5:
                valid = True

        if valid:
            item["src_start"] = round(best_s, 2)
            item["src_end"] = round(best_e, 2)
            item["match"] = round(best_score, 2)
            cursor = new_cursor
            last_end = best_e

    return sequence


def expand_boundaries(sequence):
    print("\n[2/2] 智能填缝修正...")
    for i in range(len(sequence)):
        curr = sequence[i]
        prev_end = sequence[i - 1]["src_end"] if i > 0 else 0.0

        next_start = 99999.0
        for j in range(i + 1, len(sequence)):
            if sequence[j]["src_start"] > 0.1:
                next_start = sequence[j]["src_start"]
                break

        if curr["src_start"] < 0.1:
            curr["src_start"] = round(prev_end + 0.1, 2)
            curr["src_end"] = round(
                min(next_start - 0.1, curr["src_start"] + curr["tts_dur"]), 2
            )
            print(
                f"  ID {curr['seq_id']} [补全] -> {curr['src_start']}~{curr['src_end']}"
            )
            continue

        whisper_dur = curr["src_end"] - curr["src_start"]
        needed = curr["tts_dur"]

        if whisper_dur < needed:
            deficit = needed - whisper_dur + 0.2
            gap_left = max(0, curr["src_start"] - prev_end - 0.1)
            take_left = min(gap_left, deficit)
            curr["src_start"] -= take_left
            deficit -= take_left

            if deficit > 0:
                gap_right = max(0, next_start - curr["src_end"] - 0.1)
                take_right = min(gap_right, deficit)
                curr["src_end"] += take_right

            curr["src_start"] = round(curr["src_start"], 2)
            curr["src_end"] = round(curr["src_end"], 2)
            print(
                f"  ID {curr['seq_id']} [扩张] -> 修正:{curr['src_end'] - curr['src_start']:.1f}s"
            )

    return sequence


def save_output(seq, path):
    data = [
        {
            "id": x["seq_id"],
            "role": x["role"],
            "text": x["text"],
            "filename": x["file"],
            "source_start": x["src_start"],
            "source_end": x["src_end"],
            "tts_duration": round(x["tts_dur"], 3),
            "match_score": x["match"],
        }
        for x in seq
    ]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"\n✅ 配置文件已保存: {path}")


# =======================================================
# 主入口
# =======================================================


def main():
    parser = argparse.ArgumentParser(description="ABEA V5.1 通用版")
    parser.add_argument("source_audio", help="源音频文件")
    parser.add_argument("-s", "--script", required=True, help="脚本JSON文件")
    # 允许传入多个音频文件夹
    parser.add_argument(
        "-f", "--folders", required=True, nargs="+", help="音频文件夹列表 (支持多个)"
    )
    parser.add_argument("-o", "--output", default="final_config.json")

    args = parser.parse_args()

    print("=" * 50)
    print("ABEA V5.1 - 脚本驱动通用版")
    print("=" * 50)

    # 1. 加载脚本 (真理来源)
    script = load_script_file(args.script)

    # 2. 扫描所有文件夹 (获取物理文件)
    audio_map = scan_audio_directories(args.folders)

    # 3. 合并
    sequence = merge_data(script, audio_map)
    sequence.sort(key=lambda x: x["seq_id"])

    if not sequence:
        print("❌ 未找到有效数据")
        sys.exit(1)

    print(f"准备处理 {len(sequence)} 个片段...")

    # 4. 识别与修正
    sequence = match_whisper_v3(args.source_audio, sequence)
    sequence = expand_boundaries(sequence)

    # 5. 输出
    save_output(sequence, args.output)


if __name__ == "__main__":
    main()
