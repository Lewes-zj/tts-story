#!/usr/bin/env python3
"""
ABEA 完整初始化脚本 (build_story_sequence.py) - V10.0 前瞻性智能修正版
基础架构：V5.1 通用版
核心升级：
引入"前瞻性空隙检测算法" (Lookahead Gap Detection)。
- 当 ID 3 嫌挤时，不瞎扩，而是先看 ID 4 和 ID 5。
- 如果 (ID3 + ID4) 的总时长能塞进 ID 5 之前，就大胆扩张 ID 3，并自动推迟 ID 4。
- 彻底解决重叠问题，同时保证不撞到后续的关键时间点。
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

    script_map = {}
    for item in data:
        uid = item.get("id") or item.get("sort")
        if uid is not None:
            script_map[int(uid)] = {
                "text": item.get("text", ""),
                "role": item.get("role", "未知角色"),
                # 支持读取手动锁定的时间戳
                "manual_start": item.get("start"),
                "manual_end": item.get("end"),
            }

    print(f"✅ 已加载脚本数据: {len(script_map)} 条")
    return script_map


def scan_audio_directories(folders):
    """通用扫描：只负责提取 ID 和 文件路径"""
    audio_map = {}

    for path in folders:
        if not os.path.exists(path):
            print(f"⚠️ 警告: 文件夹不存在 {path}")
            continue

        for f in os.listdir(path):
            if not f.lower().endswith((".wav", ".mp3", ".flac")):
                continue

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
    """将脚本数据注入到音频数据中"""
    sequence = []
    all_ids = sorted(audio_map.keys())

    for uid in all_ids:
        audio_info = audio_map[uid]
        script_info = script_map.get(uid)

        final_text = ""
        final_role = "未知"
        manual_start = None
        manual_end = None

        if script_info:
            final_text = script_info["text"]
            final_role = script_info["role"]
            manual_start = script_info.get("manual_start")
            manual_end = script_info.get("manual_end")
        else:
            print(f"⚠️ ID {uid} 在脚本json中未找到，将使用文件名作为文本")
            m = re.match(r"^\d+[-_](.+)\.", audio_info["file"])
            final_text = m.group(1) if m else "未知文本"
            final_role = "未定义"

        sequence.append(
            {
                "seq_id": uid,
                "role": final_role,
                "text": final_text,
                "file": audio_info["file"],
                "path": audio_info["path"],
                "tts_dur": audio_info["duration"],
                "src_start": 0.0,
                "src_end": 0.0,
                "match": 0.0,
                "manual_start": manual_start,
                "manual_end": manual_end,
            }
        )

    return sequence


# =======================================================
# 2. Whisper 匹配模块
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
        # 如果有人工锁定，直接应用并跳过识别
        if item["manual_start"] is not None:
            item["src_start"] = float(item["manual_start"])
            item["src_end"] = float(item["manual_end"])
            item["match"] = 1.0
            # 更新游标
            for idx, w in enumerate(all_words):
                if idx > cursor and w["start"] >= item["src_end"]:
                    cursor = idx
                    break
            last_end = item["src_end"]
            print(f"  ID {item['seq_id']:2d} 🔒 人工锁定")
            continue

        target = normalize(item["text"])
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


# =======================================================
# 3. 前瞻性智能修正模块 (核心算法)
# =======================================================


def smart_lookahead_expand(sequence):
    """
    [核心] 前瞻性空隙检测算法
    逻辑：当当前片段(TTS) > 识别片段(Whisper)时，
    检查 (当前TTS + 下一个TTS) 是否小于 (下下个开始时间 - 缓冲)。
    如果满足，则允许扩张当前片段，并自动推迟下一个片段。
    """
    print("\n[2/2] 执行前瞻性智能扩张 (Smart Lookahead)...")

    count = 0
    N = len(sequence)

    for i in range(N):
        curr = sequence[i]

        # 1. 基础数据准备
        # 上一句的结束时间
        prev_end = sequence[i - 1]["src_end"] if i > 0 else 0.0

        # 如果当前句没识别到(start=0)，直接尝试填入空隙（兜底逻辑）
        if curr["src_start"] < 0.1 and curr["manual_start"] is None:
            # 找下一个锚点
            next_start_limit = 99999.0
            for k in range(i + 1, N):
                if sequence[k]["src_start"] > 0.1:
                    next_start_limit = sequence[k]["src_start"]
                    break

            curr["src_start"] = round(prev_end + 0.1, 2)
            curr["src_end"] = round(
                min(next_start_limit - 0.1, curr["src_start"] + curr["tts_dur"]), 2
            )
            print(
                f"  ID {curr['seq_id']:2d} 🔧 兜底填补: {curr['src_start']}~{curr['src_end']}"
            )
            continue

        # 2. 检查是否需要扩张
        whisper_dur = curr["src_end"] - curr["src_start"]
        needed_dur = curr["tts_dur"]

        # 只有当 TTS 时长 > Whisper识别时长 + 0.1s 时才触发
        if needed_dur > whisper_dur + 0.1 and curr["manual_start"] is None:
            # === 开始前瞻 ===

            # 获取下一个片段 (Next)
            if i + 1 < N:
                next_clip = sequence[i + 1]
                next_tts_dur = next_clip["tts_dur"]
            else:
                next_clip = None
                next_tts_dur = 0

            # 获取下下个片段 (Limit) 作为硬边界
            limit_start = 99999.0
            # 从 i+2 开始找第一个有效的时间点
            for k in range(i + 2, N):
                if sequence[k]["src_start"] > 0.1:
                    limit_start = sequence[k]["src_start"]
                    break

            # 计算链式推导：
            # A. 如果当前句完整播放，需要到什么时候？
            projected_curr_end = curr["src_start"] + needed_dur

            # B. 如果下一句也紧接着完整播放，需要到什么时候？(加上 0.1s 间隔)
            projected_chain_end = projected_curr_end + 0.1 + next_tts_dur

            # === 核心判决 ===
            # 如果 (当前+下一句) 结束时间 < (硬边界 - 0.2s缓冲)
            if projected_chain_end < limit_start - 0.2:
                print(
                    f"  ID {curr['seq_id']:2d} ⚠️ 空间不足 (TTS:{needed_dur:.1f}s > Src:{whisper_dur:.1f}s)"
                )
                print(
                    f"    -> 前瞻检查: ID{curr['seq_id']} + ID{next_clip['seq_id'] if next_clip else 'End'} 预计结束于 {projected_chain_end:.1f}s"
                )
                print(f"    -> 硬边界限: {limit_start:.1f}s (安全缓冲 0.2s)")
                print(f"    -> ✅ 通过! 执行扩张与推迟...")

                # 1. 修正当前句
                # 结束时间 = 开始 + TTS时长 (不再受 Whisper 限制)
                curr["src_end"] = round(projected_curr_end, 2)

                # 2. 修正下一句 (如果有，且没被人工锁定)
                if next_clip and next_clip["manual_start"] is None:
                    # 如果下一句原本的开始时间 < 当前句修正后的结束时间
                    if next_clip["src_start"] < projected_curr_end + 0.1:
                        # 强制推迟下一句的开始
                        next_clip["src_start"] = round(projected_curr_end + 0.1, 2)

                        # 顺便把下一句的结束时间也往后推，保证它能放完
                        min_end = next_clip["src_start"] + next_clip["tts_dur"]
                        next_clip["src_end"] = round(
                            max(next_clip["src_end"], min_end), 2
                        )

                        print(
                            f"    -> 连锁修正: ID {next_clip['seq_id']} 推迟至 {next_clip['src_start']}s"
                        )

                count += 1
            else:
                # 空间不够，尝试仅向左扩张（利用上一句的空隙）
                gap_left = max(0, curr["src_start"] - prev_end - 0.1)
                deficit = needed_dur - whisper_dur

                if gap_left > 0.1:
                    take = min(gap_left, deficit)
                    curr["src_start"] -= take
                    curr["src_start"] = round(curr["src_start"], 2)
                    print(
                        f"  ID {curr['seq_id']:2d} ⚠️ 仅向左扩张 {take:.2f}s (右侧空间不足)"
                    )
                else:
                    print(f"  ID {curr['seq_id']:2d} 🚫 无法扩张 (前后均无空间)")

    print(f"\n智能修正完成: 共处理 {count} 处拥挤。\n")
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
    parser = argparse.ArgumentParser(description="ABEA V10.0 前瞻性智能修正版")
    parser.add_argument("source_audio", help="源音频文件")
    parser.add_argument("-s", "--script", required=True, help="脚本JSON文件")
    parser.add_argument(
        "-f", "--folders", required=True, nargs="+", help="音频文件夹列表 (支持多个)"
    )
    parser.add_argument("-o", "--output", default="final_config.json")

    args = parser.parse_args()

    print("=" * 50)
    print("ABEA V10.0 - 前瞻性智能修正")
    print("=" * 50)

    # 1. 加载
    script = load_script_file(args.script)
    audio_map = scan_audio_directories(args.folders)

    # 2. 合并
    sequence = merge_data(script, audio_map)
    sequence.sort(key=lambda x: x["seq_id"])

    if not sequence:
        print("❌ 未找到有效数据")
        sys.exit(1)

    print(f"准备处理 {len(sequence)} 个片段...")

    # 3. 识别
    sequence = match_whisper_v3(args.source_audio, sequence)

    # 4. 核心：前瞻性修正
    sequence = smart_lookahead_expand(sequence)

    # 5. 输出
    save_output(sequence, args.output)


if __name__ == "__main__":
    main()
