#!/usr/bin/env python3
"""
ABEA 序列构建 (V10.0 前瞻性智能修正版)
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

sys.modules["triton"] = None

try:
    import whisper
    from pydub import AudioSegment
except ImportError:
    print("错误：请安装依赖 - pip install openai-whisper pydub")
    sys.exit(1)


def normalize(text):
    return re.sub(r"[^\w]", "", text).lower()


def get_duration(path):
    try:
        return len(AudioSegment.from_file(path)) / 1000.0
    except:
        return 0.0


def load_script(path):
    if not os.path.exists(path):
        print(f"❌ 剧本文件不存在: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    script_map = {}
    for item in data:
        uid = item.get("id")
        if uid is not None:
            script_map[uid] = {
                "text": item.get("text", ""),
                "role": item.get("role", "未知"),
                "manual_start": item.get("start"),
                "manual_end": item.get("end"),
            }
    print(f"✅ 加载剧本: {len(script_map)} 条台词")
    return script_map


def scan_audio(folders):
    audio_map = {}
    for folder in folders:
        if not os.path.exists(folder):
            continue
        for f in os.listdir(folder):
            if not f.lower().endswith((".wav", ".mp3", ".flac")):
                continue
            m = re.match(r"^(\d+)[-_]", f)
            if m:
                uid = int(m.group(1))
                full_path = os.path.join(folder, f)
                audio_map[uid] = {
                    "file": f,
                    "path": full_path,
                    "dur": get_duration(full_path),
                }
    print(f"✅ 扫描音频: {len(audio_map)} 个文件")
    return audio_map


def match_whisper_base(audio_path, sequence, model="medium"):
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

    # 基础匹配，不加任何 Padding
    for item in sequence:
        if item["manual_start"] is not None:
            item["src_start"] = float(item["manual_start"])
            item["src_end"] = float(item["manual_end"])
            item["match"] = 1.0
            for idx, w in enumerate(all_words):
                if idx > cursor and w["start"] >= item["src_end"]:
                    cursor = idx
                    break
            last_end = item["src_end"]
            continue

        target = normalize(item["text"])
        search_limit = min(len(all_words), cursor + 500)

        best_s, best_e, best_score = None, None, 0.0
        new_cursor = cursor

        for idx in range(cursor, search_limit):
            phrase = ""
            for j in range(idx, min(len(all_words), idx + 80)):
                phrase += all_words[j]["word"]
                sim = SequenceMatcher(None, target, phrase).ratio()
                if sim > best_score:
                    best_score = sim
                    best_s = all_words[idx]["start"]
                    best_e = all_words[j]["end"]
                    new_cursor = j + 1
                    if sim > 0.95:
                        break
            if best_score > 0.95:
                break

        if best_s is not None and best_score > 0.35 and best_s >= last_end - 0.5:
            item["src_start"] = round(best_s, 2)
            item["src_end"] = round(best_e, 2)
            item["match"] = round(best_score, 2)
            cursor = new_cursor
            last_end = best_e
        else:
            item["src_start"] = 0.0

    return sequence


def smart_lookahead_expand(sequence):
    """
    [核心] 前瞻性空隙检测算法
    逻辑：Check (Curr + Next) < NextNext
    """
    print("\n[2/2] 执行前瞻性智能扩张 (Smart Lookahead)...")

    count = 0

    # 我们需要修改序列中的值，所以用索引遍历
    # 遍历到倒数第二个，因为需要 check next
    N = len(sequence)

    for i in range(N):
        curr = sequence[i]

        # 如果没识别到，或者有人工锁定的，跳过
        if curr["src_start"] < 0.1 or curr["manual_start"] is not None:
            continue

        whisper_dur = curr["src_end"] - curr["src_start"]
        needed_dur = curr["tts_dur"]

        # 只有当 TTS 比 Whisper 识别的长时，才需要扩张
        if needed_dur > whisper_dur + 0.1:  # 0.1s 误差容忍
            # === 开始前瞻 ===

            # 获取下一个片段 (Next)
            if i + 1 < N:
                next_clip = sequence[i + 1]
                next_tts_dur = next_clip["tts_dur"]
            else:
                next_clip = None
                next_tts_dur = 0

            # 获取下下个片段 (Limit)
            limit_start = 99999.0
            for k in range(i + 2, N):
                if sequence[k]["src_start"] > 0.1:
                    limit_start = sequence[k]["src_start"]
                    break

            # 计算链式推导：
            # 如果当前句完整播放，需要到什么时候？
            projected_curr_end = curr["src_start"] + needed_dur

            # 如果下一句也紧接着完整播放，需要到什么时候？
            # 加上 0.1s 间隔
            projected_chain_end = projected_curr_end + 0.1 + next_tts_dur

            # === 核心判决 ===
            # 如果 (当前+下一句) 结束时间 < (下下句开始 - 0.3s缓冲)
            if projected_chain_end < limit_start - 0.3:
                print(
                    f"  ID {curr['seq_id']:2d} ⚠️ 空间不足 (TTS:{needed_dur:.1f}s > Src:{whisper_dur:.1f}s)"
                )
                print(
                    f"    -> 前瞻检查: ID {curr['seq_id']} + ID {next_clip['seq_id'] if next_clip else 'End'} 总长约 {projected_chain_end - curr['src_start']:.1f}s"
                )
                print(
                    f"    -> 可用空间: {limit_start - curr['src_start']:.1f}s (至 ID {sequence[min(i + 2, N - 1)]['seq_id']})"
                )
                print(f"    -> ✅ 通过! 执行扩张与推迟...")

                # 1. 修正当前句
                # 结束时间 = 开始 + TTS时长 (不再受 Whisper 限制)
                curr["src_end"] = round(projected_curr_end, 2)

                # 2. 修正下一句 (如果有，且没被人工锁定)
                if next_clip and next_clip["manual_start"] is None:
                    # 如果下一句原本的开始时间 < 当前句修正后的结束时间
                    if next_clip["src_start"] < projected_curr_end + 0.1:
                        old_start = next_clip["src_start"]
                        # 强制推迟下一句的开始
                        next_clip["src_start"] = round(projected_curr_end + 0.1, 2)
                        # 顺便把下一句的结束时间也往后推，保持它的原有持续时长(或者TTS时长)
                        # 这里我们保守一点，保证它至少能放完它的TTS
                        min_end = next_clip["src_start"] + next_clip["tts_dur"]
                        next_clip["src_end"] = round(
                            max(next_clip["src_end"], min_end), 2
                        )

                        print(
                            f"    -> 连锁修正: ID {next_clip['seq_id']} 推迟至 {next_clip['src_start']}s"
                        )

                count += 1
            else:
                # 空间不够，不敢动
                print(
                    f"  ID {curr['seq_id']:2d} 🚫 扩张失败: 会撞到后续节点 (需 {projected_chain_end:.1f}s > 限 {limit_start:.1f}s)"
                )

    print(f"\n智能修正完成: 共处理 {count} 处拥挤。\n")
    return sequence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_audio")
    parser.add_argument("-s", "--script", required=True)
    parser.add_argument("-f", "--folders", required=True, nargs="+")
    parser.add_argument("-o", "--output", default="final_config.json")
    args = parser.parse_args()

    script_map = load_script(args.script)
    audio_map = scan_audio(args.folders)

    sequence = []
    for uid in sorted(audio_map.keys()):
        s = script_map.get(uid, {})
        a = audio_map[uid]
        sequence.append(
            {
                "seq_id": uid,
                "role": s.get("role", "未知"),
                "text": s.get("text", "未知"),
                "manual_start": s.get("manual_start"),
                "manual_end": s.get("manual_end"),
                "file": a["file"],
                "path": a["path"],
                "tts_dur": a["dur"],
                "src_start": 0.0,
                "src_end": 0.0,
                "match": 0.0,
            }
        )

    # 1. 基础识别 (不加 Padding)
    sequence = match_whisper_base(args.source_audio, sequence)

    # 2. 前瞻性智能扩张 (你的算法)
    sequence = smart_lookahead_expand(sequence)

    # 保存
    data = [
        {
            "id": x["seq_id"],
            "role": x["role"],
            "text": x["text"],
            "filename": x["file"],
            "source_start": x["src_start"],
            "source_end": x["src_end"],
            "tts_duration": x["tts_dur"],
            "match_score": x["match"],
        }
        for x in sequence
    ]

    data.sort(key=lambda x: x["id"])
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"\n✅ 已保存: {args.output}")


if __name__ == "__main__":
    main()
