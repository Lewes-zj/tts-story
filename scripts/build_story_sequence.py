#!/usr/bin/env python3
"""
ABEA 完整初始化脚本 (build_story_sequence.py) - 自动排序版
功能：基于文件名的全局序号 (ID)，自动合并旁白和对话文件夹，构建故事序列。
"""

import os
import sys
import re
import json
import argparse
from difflib import SequenceMatcher

# 强制禁用 Triton 以防报错
sys.modules["triton"] = None

try:
    import whisper
    from pydub import AudioSegment
except ImportError:
    print("错误：请安装依赖 - pip install openai-whisper pydub")
    sys.exit(1)


def get_duration(path):
    """获取音频时长(秒)"""
    try:
        return len(AudioSegment.from_file(path)) / 1000.0
    except:
        return 0


def clean_text(text):
    """
    清洗文本：移除角色前缀，用于文本匹配
    例如: "HS-原来是你" -> "原来是你"
    """
    # 移除常见的角色前缀模式 (HS-, STF_, etc.)
    text = re.sub(r"^(HS|STF|Watson|Sherlock)[-_]", "", text, flags=re.IGNORECASE)
    return text


def parse_role(filename, default_role="旁白"):
    """
    根据文件名判断角色
    """
    filename_upper = filename.upper()
    if "HS" in filename_upper or "WATSON" in filename_upper:
        return "华生"
    elif (
        "STF" in filename_upper
        or "SHERLOCK" in filename_upper
        or "HOLMES" in filename_upper
    ):
        return "斯坦福"
    return default_role


def scan_folder(folder_path, file_type):
    """
    通用扫描函数
    file_type: 'narrator' 或 'dialogue'
    """
    clips = []

    if not os.path.exists(folder_path):
        print(f"⚠️ 警告: 文件夹不存在: {folder_path}")
        return clips

    print(f"正在扫描 {file_type} 文件夹: {folder_path}")

    for f in os.listdir(folder_path):
        if not f.lower().endswith((".wav", ".mp3", ".flac", ".m4a")):
            continue

        # 正则匹配：支持 "10-xxx.wav" 或 "11_HS_xxx.wav"
        # group(1): ID
        # group(2): 剩余文本部分
        match = re.match(r"^(\d+)[-_](.+)\.(wav|mp3|flac|m4a)$", f, re.IGNORECASE)

        if match:
            seq_id = int(match.group(1))
            raw_text = match.group(2)

            # 自动判断角色
            if file_type == "narrator":
                role = "旁白"
            else:
                role = parse_role(f, default_role="未知角色")

            # 清洗文本 (移除文件名里的 HS- 等前缀，保留纯文本用于匹配)
            clean_content = clean_text(raw_text)

            clips.append(
                {
                    "seq_id": seq_id,
                    "type": file_type,
                    "role": role,
                    "text": clean_content,
                    "file": f,
                    "path": os.path.join(folder_path, f),
                    "tts_dur": get_duration(os.path.join(folder_path, f)),
                }
            )

    return clips


# 简繁转换表 (用于Whisper匹配)
T2S = str.maketrans(
    "個們這裡來時後說東車開門書長間點過頭話問題實現發認為從無還進動種對應關視機場愛務員會議論語學習號碼條約記錄製導師範圍繞線圖館員警連續劇場邊緣聯繫統計畫處據應該準備隨測試驗證環節擊選擇輸戰鬥練庫區塊鏈網絡遊戲開課程視頻頻道訂閱評轉發贊註冊登錄帳設置歷史搜索結果頁顯詳細聯電郵箱址導菜單欄側頂底標題內容摘縮略封背景顏色字體樣佈排距框陰畫渡響適兼瀏覽設備屏幕辨橫豎觸摸滑雙擊縮旋轉拖釋醫學習題",
    "个们这里来时后说东车开门书长间点过头话问题实现发认为从无还进动种对应关视机场爱务员会议论语学习号码条约记录制导师范围绕线图馆员警连续剧场边缘联系统计划处据应该准备随测试验证环节击选择输战斗练库区块链网络游戏开课程视频频道订阅评转发赞注册登录帐设置历史搜索结果页显详细联电邮箱址导菜单栏侧顶底标题内容摘缩略封背景颜色字体样布排距框阴画渡响适兼浏览设备屏幕辨横竖触摸滑双击缩旋转拖释医学习题",
)


def normalize(text):
    return re.sub(r"[^\w]", "", text).lower()


def text_similarity(t1, t2):
    return SequenceMatcher(None, normalize(t1), normalize(t2)).ratio()


def to_simp(t):
    return t.translate(T2S)


# 在 build_story_sequence.py 中替换此函数


def match_whisper(audio_path, sequence, model="medium"):
    """
    Whisper时间戳匹配 (V3.0 修复版)
    核心修复：强制游标 cursor 向前推进，防止时间戳回滚
    """
    print(f"\n正在加载 Whisper 模型 ({model})...")
    m = whisper.load_model(model)

    print(f"正在转录源音频: {audio_path}")
    res = m.transcribe(audio_path, language="zh", word_timestamps=True, verbose=False)

    # 1. 展平 Word 列表
    all_words = []
    for seg in res.get("segments", []):
        for word_info in seg.get("words", []):
            clean_w = normalize(word_info["word"])
            if clean_w:
                all_words.append(
                    {
                        "word": clean_w,
                        "start": word_info["start"],
                        "end": word_info["end"],
                    }
                )

    print(f"识别出 {len(all_words)} 个单词，总时长 {res['segments'][-1]['end']:.1f}s")

    # 游标：指向 all_words 中当前搜索的起始位置
    cursor = 0

    # 上一句的结束时间（用于兜底）
    last_valid_end_time = 0.0

    print("\n开始匹配时间戳 (强制递增版)...")

    for idx, item in enumerate(sequence):
        target_text = normalize(item["text"])
        target_len = len(target_text)

        # 预估这句话大概包含多少个词 (假设平均一个词 1-2 个字)
        # 这个窗口大小不是死的，只是为了提取 text
        approx_word_count = max(1, len(target_text))

        best_start = None
        best_end = None
        best_score = -1.0
        best_end_index = cursor  # 记录最佳匹配结束时的单词索引

        # === 搜索窗口 ===
        # 范围：从游标 cursor 开始，往后找 100 个词 (防止跨度太大)
        search_range = min(len(all_words), cursor + 100)

        for i in range(cursor, search_range):
            # 尝试组合接下来的一段词
            # 我们动态调整组合长度，尝试匹配目标文本
            current_phrase = ""
            current_end_idx = i

            # 内层循环：拼凑单词，直到长度接近目标文本
            for j in range(i, min(len(all_words), i + 30)):  # 一句话最多拼30个词
                current_phrase += all_words[j]["word"]
                current_end_idx = j

                # 如果拼凑的长度已经大大超过目标文本，就没必要继续拼了
                if len(current_phrase) > target_len + 5:
                    break

                # 计算相似度
                sim = SequenceMatcher(None, target_text, current_phrase).ratio()

                if sim > best_score:
                    best_score = sim
                    best_start = all_words[i]["start"]
                    best_end = all_words[current_end_idx]["end"]
                    best_end_index = current_end_idx + 1  # 指向下一个词

        # === 决策逻辑 ===

        # 判定是否为有效匹配
        # 1. 分数要及格 (比如 > 0.4)
        # 2. 或者分数虽然低点，但时间顺序是合理的 (>= 上一句结束时间)
        is_valid = False
        if best_start is not None:
            if best_score > 0.5:
                is_valid = True
            elif best_score > 0.3 and best_start >= last_valid_end_time:
                is_valid = True

        if is_valid:
            # 采纳匹配结果
            item["src_start"] = round(best_start, 3)
            item["src_end"] = round(best_end, 3)
            item["match"] = round(best_score, 2)

            # 关键：更新游标！让下一次搜索从这里开始
            cursor = best_end_index
            last_valid_end_time = best_end

            status = "✅"
        else:
            # 匹配失败 (可能源音频这段是纯音乐，或者Whisper没识别出来)
            # 兜底策略：紧接着上一句后面，给一个估算时间
            # 假设语速 4字/秒
            est_duration = max(1.0, len(target_text) * 0.25)

            item["src_start"] = round(last_valid_end_time + 0.1, 3)
            item["src_end"] = round(last_valid_end_time + 0.1 + est_duration, 3)
            item["match"] = 0.0

            # 这种情况下，游标不乱动，或者只稍微往前挪一点点
            # 但为了防止死循环，我们还是得更新 last_valid_end_time
            last_valid_end_time = item["src_end"]
            status = "⚠️"

        item["tts_dur"] = get_duration(item["path"])
        label = f"{item['role']}"
        print(
            f"  {item['seq_id']:2d}. {status} {label:8s} {item['src_start']:6.2f}s (分:{item['match']:.2f}) {item['text'][:10]}..."
        )

    return sequence


def save_config(seq, out):
    """保存为 JSON 格式"""
    data = [
        {
            "id": i["seq_id"],
            "type": i["type"],
            "role": i["role"],
            "text": i["text"],
            "filename": i["file"],
            "source_start": i["src_start"],
            "source_end": i["src_end"],
            "tts_duration": round(i["tts_dur"], 3),
            "alignment_type": "FLOATING",
            "match_score": i["match"],
        }
        for i in seq
    ]

    # 保存前再按 ID 确保排序一次
    data.sort(key=lambda x: x["id"])

    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"\n已保存配置文件: {out} ({len(data)} 条片段)")


def main():
    parser = argparse.ArgumentParser(description="ABEA 完整序列构建 (自动排序版)")

    parser.add_argument("source_audio", help="源音频文件路径 (例如: source.mp3)")
    parser.add_argument("-n", "--narrator", required=True, help="旁白音频文件夹路径")
    parser.add_argument("-d", "--dialogue", required=True, help="对话音频文件夹路径")
    parser.add_argument(
        "-o", "--output", default="alignment_config_full.json", help="输出JSON文件名"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("ABEA 故事序列构建 (ID自动排序版)")
    print("=" * 50)

    if not os.path.exists(args.source_audio):
        print(f"❌ 错误: 源音频文件不存在: {args.source_audio}")
        sys.exit(1)

    # 1. 分别扫描两个文件夹
    narrator_clips = scan_folder(args.narrator, "narrator")
    dialogue_clips = scan_folder(args.dialogue, "dialogue")

    print(f"\n扫描结果: 旁白 {len(narrator_clips)} 个, 对话 {len(dialogue_clips)} 个")

    if not narrator_clips and not dialogue_clips:
        print("❌ 错误: 两个文件夹里都没找到有效音频。")
        sys.exit(1)

    # 2. 合并并排序 (核心逻辑)
    full_sequence = narrator_clips + dialogue_clips
    # 按照 seq_id (文件名开头的数字) 进行排序
    full_sequence.sort(key=lambda x: x["seq_id"])

    print(f"合并后序列总长: {len(full_sequence)} 个片段")

    # 简单的ID连续性检查 (可选)
    ids = [x["seq_id"] for x in full_sequence]
    if len(ids) != len(set(ids)):
        print("⚠️ 警告: 发现重复的序号 ID！请检查文件名是否冲突。")

    # 3. Whisper 匹配时间戳
    full_sequence = match_whisper(args.source_audio, full_sequence)

    # 4. 保存
    save_config(full_sequence, args.output)

    print("\n完成!")


if __name__ == "__main__":
    main()
