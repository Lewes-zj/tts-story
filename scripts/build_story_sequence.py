#!/usr/bin/env python3
"""
ABEA 序列构建 (V8.0 声学精修版)
核心升级：
1. [Whisper 定位]：利用 script.json 长文本获取粗略时间。
2. [声学精修]：引入 VAD (能量检测) 机制。
   - Whisper 说 10.44s 开始？
   - 程序检查 10.44s 往前是不是真的静音？
   - 发现 10.0s 处有声音能量 -> 修正为 10.0s。
   - 彻底解决 Whisper "吞头去尾" 导致的对齐不准。
"""

import os
import sys
import re
import json
import argparse
from difflib import SequenceMatcher

# 禁用 Triton
sys.modules["triton"] = None

try:
    import whisper
    from pydub import AudioSegment, silence
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
                # 支持人工强行锁定
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


# =======================================================
# 核心：Whisper 识别
# =======================================================


def match_whisper(audio_path, sequence, model="medium"):
    print(f"\n[1/3] Whisper 识别中 ({model})...")
    m = whisper.load_model(model)
    res = m.transcribe(audio_path, language="zh", word_timestamps=True, verbose=False)

    all_words = []
    for s in res["segments"]:
        for w in s["words"]:
            all_words.append(
                {"word": normalize(w["word"]), "start": w["start"], "end": w["end"]}
            )

    print(f"识别单词数: {len(all_words)}")

    cursor = 0
    last_end = 0.0

    print("\n[2/3] 文本匹配...")
    for item in sequence:
        # 如果有人工锁定，跳过识别
        if item["manual_start"] is not None:
            item["src_start"] = float(item["manual_start"])
            item["src_end"] = float(item["manual_end"])
            item["match"] = 1.0
            print(
                f"  ID {item['seq_id']:2d} 🔒 人工锁定: {item['src_start']}~{item['src_end']}"
            )

            # 更新游标，避免后面的识别乱套
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

        for i in range(cursor, search_limit):
            phrase = ""
            for j in range(i, min(len(all_words), i + 80)):
                phrase += all_words[j]["word"]
                sim = SequenceMatcher(None, target, phrase).ratio()

                if sim > best_score:
                    best_score = sim
                    best_s = all_words[i]["start"]
                    best_e = all_words[j]["end"]
                    new_cursor = j + 1
                    if sim > 0.9:
                        break
            if best_score > 0.9:
                break

        valid = False
        if best_s is not None:
            if best_score > 0.3 and best_s >= last_end - 0.5:
                valid = True

        if valid:
            item["src_start"] = round(best_s, 2)
            item["src_end"] = round(best_e, 2)
            item["match"] = round(best_score, 2)
            cursor = new_cursor
            last_end = best_e
        else:
            item["src_start"] = 0.0  # 没找到

    return sequence


# =======================================================
# 核心升级：声学精修 (Acoustic Refinement)
# =======================================================


def refine_timestamps(sequence, audio_path):
    """
    拿着显微镜(pydub)去检查 Whisper 找到的时间点
    如果发现时间点前后还有声音能量，说明 Whisper 漏听了，进行物理修正。
    """
    print("\n[3/3] 声学精修 (检测真实音频边缘)...")

    # 加载整段源音频 (注意内存消耗，源音频很大可能需要切片读，这里简化处理)
    print("正在加载源音频波形数据...")
    full_audio = AudioSegment.from_file(audio_path)

    # 静音阈值 (dBFS)
    # 这个值很关键，-45 到 -50 通常能检测到呼吸声，太高会漏，太低会把底噪当声音
    SILENCE_THRESH = -50

    for i, item in enumerate(sequence):
        # 跳过没识别到的 或 人工锁定的
        if item["src_start"] < 0.1 or item["manual_start"] is not None:
            continue

        # 1. 确定搜索的安全边界 (不能侵入上一句的领地)
        prev_limit = sequence[i - 1]["src_end"] if i > 0 else 0.0
        # 给上一句留 0.1s 的安全距离
        prev_limit += 0.1

        original_start = item["src_start"]
        original_end = item["src_end"]

        # === 修正开始时间 (向左探测) ===
        # 截取一段：[Whisper起点 - 2秒, Whisper起点]
        check_start = max(prev_limit, original_start - 2.0)
        if check_start < original_start:
            segment = full_audio[int(check_start * 1000) : int(original_start * 1000)]

            # 倒着找：从 Whisper 起点往回找，直到遇到静音
            # pydub 的 detect_leading_silence 是从头找，所以我们先把音频反转
            rev_seg = segment.reverse()
            silence_len = silence.detect_leading_silence(
                rev_seg, silence_threshold=SILENCE_THRESH, chunk_size=10
            )

            # 声音持续的长度 = 片段总长 - 头部静音(反转后的头部=实际的尾部)
            sound_duration = (len(segment) - silence_len) / 1000.0

            if sound_duration > 0.05:
                # 意味着 Whisper 起点之前，还有 sound_duration 长度的声音
                new_start = original_start - sound_duration
                # 再次校准，不要太激进
                new_start = max(prev_limit, new_start)

                item["src_start"] = round(new_start, 2)
                print(
                    f"  ID {item['seq_id']:2d} 👈 修正开始: {original_start:.2f}s -> {new_start:.2f}s (找回 {original_start - new_start:.2f}s)"
                )

        # === 修正结束时间 (向右探测) ===
        # 截取一段：[Whisper终点, Whisper终点 + 2秒]
        # 下一句的开始时间是硬边界
        next_limit = 99999.0
        for j in range(i + 1, len(sequence)):
            if sequence[j]["src_start"] > 0.1:
                next_limit = sequence[j]["src_start"] - 0.1
                break

        check_end = min(next_limit, original_end + 2.0)

        if check_end > original_end:
            segment = full_audio[int(original_end * 1000) : int(check_end * 1000)]

            # 正着找：从 Whisper 终点往后找，直到遇到静音
            silence_start = silence.detect_leading_silence(
                segment, silence_threshold=SILENCE_THRESH, chunk_size=10
            )

            # 静音开始的位置就是声音结束的位置
            # 如果 silence_start == len(segment)，说明这段全是声音（或者没找到静音），那就全都要
            # 如果 silence_start == 0，说明 Whisper 终点之后立刻就是静音，无需修正

            found_extra = silence_start / 1000.0

            if found_extra > 0.05:
                new_end = original_end + found_extra
                item["src_end"] = round(new_end, 2)
                print(
                    f"  ID {item['seq_id']:2d} 👉 修正结束: {original_end:.2f}s -> {new_end:.2f}s (找回 {new_end - original_end:.2f}s)"
                )

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
                "manual_start": s.get("manual_start"),  # 传递人工标记
                "manual_end": s.get("manual_end"),
                "file": a["file"],
                "path": a["path"],
                "tts_dur": a["dur"],
                "src_start": 0.0,
                "src_end": 0.0,
                "match": 0.0,
            }
        )

    # 1. 先用 Whisper 找大概位置
    sequence = match_whisper(args.source_audio, sequence)

    # 2. 再用波形精修具体边缘 (关键步骤)
    sequence = refine_timestamps(sequence, args.source_audio)

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
    print(f"\n✅ 配置文件已保存: {args.output}")


if __name__ == "__main__":
    main()
