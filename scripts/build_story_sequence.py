#!/usr/bin/env python3
"""
ABEA 完整初始化脚本 (build_story_sequence.py) - V5.2 纯净脚本驱动版
特点：
1. [数据源] 文本来自 script.json (全文本)，音频来自文件夹扫描。
2. [通用性] 角色信息完全解耦，由 json 定义。
3. [纯净性] 移除所有"填缝/扩张"算法，完全展示 Whisper 对长文本的原始匹配结果。
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
# 1. 数据加载模块
# =======================================================


def load_script_file(json_path):
    """读取 script.json"""
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
            }

    print(f"✅ 已加载脚本数据: {len(script_map)} 条")
    return script_map


def scan_audio_directories(folders):
    """扫描音频文件夹，建立 ID 索引"""
    audio_map = {}

    for path in folders:
        if not os.path.exists(path):
            print(f"⚠️ 警告: 文件夹不存在 {path}")
            continue

        for f in os.listdir(path):
            if not f.lower().endswith((".wav", ".mp3", ".flac")):
                continue

            # 解析 ID (例如: 21-xxx.wav)
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
    """合并脚本与音频信息"""
    sequence = []
    all_ids = sorted(audio_map.keys())

    for uid in all_ids:
        audio_info = audio_map[uid]
        script_info = script_map.get(uid)

        # 优先使用脚本中的长文本和角色
        if script_info:
            final_text = script_info["text"]
            final_role = script_info["role"]
            source = "Script"
        else:
            # 兜底：如果没有脚本，尝试从文件名解析
            print(f"⚠️ ID {uid} 未在脚本中找到，使用文件名兜底")
            m = re.match(r"^\d+[-_](.+)\.", audio_info["file"])
            final_text = m.group(1) if m else "未知文本"
            final_role = "未定义"
            source = "Filename"

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
            }
        )

        # 调试打印：检查关键的 ID 21 是否用上了长文本
        if uid == 21:
            print(f"  [ID 21] 匹配源: {source} | 文本: {final_text[:20]}...")

    return sequence


# =======================================================
# 2. Whisper 匹配模块 (纯净版)
# =======================================================


def match_whisper_pure(audio_path, sequence, model="medium"):
    print(f"\n[Whisper] 正在识别源音频 ({model})...")
    m = whisper.load_model(model)

    # 获取单词级时间戳
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

    print("\n开始匹配时间轴...")

    for item in sequence:
        target = normalize(item["text"])
        # 搜索窗口
        search_limit = min(len(all_words), cursor + 300)

        best_s, best_e, best_score = None, None, 0
        new_cursor = cursor

        # 暴力搜索最佳匹配段落
        for i in range(cursor, search_limit):
            phrase = ""
            # 因为是长文本，尝试拼凑更多的词
            for j in range(i, min(len(all_words), i + 60)):
                phrase += all_words[j]["word"]
                sim = SequenceMatcher(None, target, phrase).ratio()

                if sim > best_score:
                    best_score = sim
                    best_s = all_words[i]["start"]
                    best_e = all_words[j]["end"]
                    new_cursor = j + 1

                    # 如果匹配度非常高，直接锁定
                    if sim > 0.90:
                        break
            if best_score > 0.90:
                break

        # 判定逻辑：只要不是错得离谱(时间倒流)，就采纳原始结果
        valid = False
        if best_s is not None:
            if best_score > 0.4 and best_s >= last_end - 0.5:
                valid = True

        if valid:
            item["src_start"] = round(best_s, 3)
            item["src_end"] = round(best_e, 3)
            item["match"] = round(best_score, 2)

            # 更新游标
            cursor = new_cursor
            last_end = best_e
            status = "✅"
        else:
            # 没匹配到也不瞎猜，保持 0，方便人工排查
            status = "❌"

        print(
            f"  ID {item['seq_id']:2d} {status} {item['src_start']:6.2f}s~{item['src_end']:6.2f}s (分:{item['match']:.2f})"
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

    # 最终按 ID 排序
    data.sort(key=lambda x: x["id"])

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"\n✅ 配置文件已保存: {path}")


# =======================================================
# 主入口
# =======================================================


def main():
    parser = argparse.ArgumentParser(description="ABEA V5.2 纯净版")
    parser.add_argument("source_audio", help="源音频文件")
    parser.add_argument("-s", "--script", required=True, help="脚本JSON文件")
    parser.add_argument(
        "-f", "--folders", required=True, nargs="+", help="音频文件夹列表"
    )
    parser.add_argument("-o", "--output", default="final_config.json")

    args = parser.parse_args()

    print("=" * 50)
    print("ABEA V5.2 - 纯净脚本驱动版")
    print("=" * 50)

    # 1. 加载资源
    script = load_script_file(args.script)
    audio_map = scan_audio_directories(args.folders)

    # 2. 合并信息
    sequence = merge_data(script, audio_map)
    sequence.sort(key=lambda x: x["seq_id"])

    if not sequence:
        print("❌ 未找到有效数据")
        sys.exit(1)

    # 3. 执行纯净匹配 (无填缝)
    sequence = match_whisper_pure(args.source_audio, sequence)

    # 4. 输出
    save_output(sequence, args.output)


if __name__ == "__main__":
    main()
