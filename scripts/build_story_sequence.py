#!/usr/bin/env python3
"""
ABEA 完整初始化脚本 (build_story_sequence.py.py) - JSON版
基于TTS文件实际命名，构建旁白+对话的完整序列
"""

import os
import sys
import re
import json
from difflib import SequenceMatcher

try:
    import whisper
    from pydub import AudioSegment
except ImportError:
    print("错误：请安装依赖 - pip install openai-whisper pydub")
    sys.exit(1)


# 定义对话插入位置（基于旁白ID后插入）
DIALOGUE_INSERTION = {
    11: ("STF", "华生先生你怎么在这里"),  # "小斯坦夫热情的大喊一声：" 之后
    14: ("HS", "原来是你"),  # "他也很惊喜，高兴的说：" 之后
    20: ("STF", "华生先生你怎么在伦敦"),  # "小斯坦夫很开心的说：" 之后
    21: ("HS", "嗯这个说来话长"),  # "华生也是惊喜加意外...说：" 之后
    22: ("STF", "好啊好啊"),  # "小斯坦夫很高兴说：" 之后
    31: ("STF", "华生先生你最近到底"),  # "他好奇的问：" 之后
    # 32: ('HS', '我受了很重的伤'),           # 缺少这个对话文件
    36: ("STF", "您不是去读医学博士"),  # "他想了想，选了一个。" 之后
    37: ("HS", "没错我是去读博士"),  # "他拍了拍...说：" 之后
}


def normalize(text):
    return re.sub(r"[^\w]", "", text).lower()


def text_similarity(t1, t2):
    return SequenceMatcher(None, normalize(t1), normalize(t2)).ratio()


def scan_tts_files(folder):
    """扫描TTS文件"""
    narrator = {}
    dialogue = {}

    for f in os.listdir(folder):
        if not f.lower().endswith((".wav", ".mp3")):
            continue

        path = os.path.join(folder, f)

        # 旁白: 数字-文本.wav
        m = re.match(r"^(\d+)-(.+)\.(wav|mp3)$", f, re.IGNORECASE)
        if m:
            narrator[int(m.group(1))] = {"file": f, "path": path, "text": m.group(2)}
            continue

        # 对话: HS-xxx 或 STF-xxx
        if f.startswith("HS-"):
            key = f[3:].replace(".WAV", "").replace(".wav", "").replace(".mp3", "")
            dialogue[("HS", key)] = {
                "file": f,
                "path": path,
                "text": key,
                "role": "华生",
            }
        elif f.startswith("STF-"):
            key = f[4:].replace(".WAV", "").replace(".wav", "").replace(".mp3", "")
            dialogue[("STF", key)] = {
                "file": f,
                "path": path,
                "text": key,
                "role": "斯坦福",
            }

    return narrator, dialogue


def find_dialogue_file(dialogue_files, prefix, keyword):
    """根据前缀和关键词找对话文件"""
    best = None
    best_score = 0

    for (p, text), info in dialogue_files.items():
        if p != prefix:
            continue
        score = text_similarity(keyword, text)
        if score > best_score:
            best_score = score
            best = info

    return best if best_score > 0.3 else None


def build_sequence(narrator, dialogue):
    """构建完整序列"""
    seq = []
    seq_id = 1

    for nid in sorted(narrator.keys()):
        # 添加旁白
        n = narrator[nid]
        seq.append(
            {
                "seq_id": seq_id,
                "type": "narrator",
                "role": "旁白",
                "text": n["text"],
                "file": n["file"],
                "path": n["path"],
                "narrator_id": nid,
            }
        )
        seq_id += 1

        # 检查是否需要插入对话
        if nid in DIALOGUE_INSERTION:
            prefix, keyword = DIALOGUE_INSERTION[nid]
            dlg = find_dialogue_file(dialogue, prefix, keyword)
            if dlg:
                seq.append(
                    {
                        "seq_id": seq_id,
                        "type": "dialogue",
                        "role": dlg["role"],
                        "text": dlg["text"],
                        "file": dlg["file"],
                        "path": dlg["path"],
                        "after_narrator": nid,
                    }
                )
                seq_id += 1
                print(f"  旁白 {nid} 后插入对话: [{dlg['role']}] {dlg['text'][:20]}...")
            else:
                print(f"  警告: 旁白 {nid} 后未找到对话 ({prefix}-{keyword})")

    return seq


def get_duration(path):
    try:
        return len(AudioSegment.from_file(path)) / 1000.0
    except:
        return 0


# 简繁转换
T2S = str.maketrans(
    "個們這裡來時後說東車開門書長間點過頭話問題實現發認為從無還進動種對應關視機場愛務員會議論語學習號碼條約記錄製導師範圍繞線圖館員警連續劇場邊緣聯繫統計畫處據應該準備隨測試驗證環節擊選擇輸戰鬥練庫區塊鏈網絡遊戲開課程視頻頻道訂閱評轉發贊註冊登錄帳設置歷史搜索結果頁顯詳細聯電郵箱址導菜單欄側頂底標題內容摘縮略封背景顏色字體樣佈排距框陰畫渡響適兼瀏覽設備屏幕辨橫豎觸摸滑雙擊縮旋轉拖釋醫學習題",
    "个们这里来时后说东车开门书长间点过头话问题实现发认为从无还进动种对应关视机场爱务员会议论语学习号码条约记录制导师范围绕线图馆员警连续剧场边缘联系统计划处据应该准备随测试验证环节击选择输战斗练库区块链网络游戏开课程视频频道订阅评转发赞注册登录帐设置历史搜索结果页显详细联电邮箱址导菜单栏侧顶底标题内容摘缩略封背景颜色字体样布排距框阴画渡响适兼浏览设备屏幕辨横竖触摸滑双击缩旋转拖释医学习题",
)


def to_simp(t):
    return t.translate(T2S)


def match_whisper(audio_path, sequence, model="medium"):
    """Whisper时间戳匹配"""
    print(f"\n加载 Whisper ({model})...")
    m = whisper.load_model(model)

    print(f"转录: {audio_path}")
    res = m.transcribe(audio_path, language="zh", word_timestamps=True, verbose=False)
    segs = res.get("segments", [])
    print(f"识别 {len(segs)} 段, 总时长 {segs[-1]['end']:.1f}s")

    widx = 0

    for item in sequence:
        txt = item["text"]
        best_start, best_end, best_score = None, None, 0

        for si in range(max(0, widx - 3), min(len(segs), widx + 12)):
            combined = ""
            for ei in range(si, min(si + 5, len(segs))):
                combined += segs[ei]["text"]
                s = text_similarity(txt, to_simp(combined))
                if s > best_score:
                    best_score = s
                    best_start = segs[si]["start"]
                    best_end = segs[ei]["end"]
                    widx = ei + 1
                if s > 0.75:
                    break
            if best_score > 0.75:
                break

        item["src_start"] = round(best_start, 3) if best_start else 0
        item["src_end"] = round(best_end, 3) if best_end else 0
        item["match"] = round(best_score, 2)
        item["tts_dur"] = get_duration(item["path"])

        label = "旁白" if item["type"] == "narrator" else f"对话[{item['role']}]"
        print(
            f"  {item['seq_id']:2d}. {label:12s} {item['src_start']:6.1f}s~{item['src_end']:6.1f}s ({item['match']:.2f}) {txt[:22]}..."
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

    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"\n已保存: {out} ({len(data)} 条)")


def main():
    print("=" * 50)
    print("ABEA 完整初始化 (旁白+对话) - JSON版")
    print("=" * 50)

    narrator, dialogue = scan_tts_files("tts音频积木")
    print(f"\n旁白: {len(narrator)} 个, 对话: {len(dialogue)} 个")

    print("\n构建序列...")
    seq = build_sequence(narrator, dialogue)
    print(f"完整序列: {len(seq)} 个片段")

    seq = match_whisper("纯人声.mp3", seq)
    save_config(seq, "alignment_config_full.json")

    print("\n完成! 请检查 alignment_config_full.json")


if __name__ == "__main__":
    main()
