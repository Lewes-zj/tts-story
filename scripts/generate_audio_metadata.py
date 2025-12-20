import os
import json
import re
import argparse
import sys


def extract_info(filename):
    """
    从文件名中提取 id 和 text。
    支持的文件名格式：
    1. "1-很久以前.wav" -> id: 1, text: "很久以前"
    2. "1_很久以前.wav" -> id: 1, text: "很久以前"
    """
    # 移除文件扩展名
    name_without_ext = os.path.splitext(filename)[0]

    # 尝试匹配 "数字-文本" 或 "数字_文本" 的格式
    match = re.match(r"^(\d+)[-_](.+)$", name_without_ext)

    if match:
        return int(match.group(1)), match.group(2)

    return None, None


def generate_metadata(audio_dir, output_file):
    """
    扫描音频目录并生成 metadata json 文件
    """
    # 检查输入目录是否存在
    if not os.path.exists(audio_dir):
        print(f"❌ 错误: 输入文件夹不存在: {audio_dir}")
        sys.exit(1)

    metadata_list = []

    # 遍历目录中的文件
    print(f"📂 正在扫描目录: {audio_dir} ...")
    files = os.listdir(audio_dir)

    # 过滤出音频文件 (wav, mp3, flac)
    audio_files = [f for f in files if f.lower().endswith((".wav", ".mp3", ".flac"))]

    if not audio_files:
        print("⚠️  警告: 目录中未找到音频文件。")
        return

    valid_count = 0
    for filename in audio_files:
        file_id, text = extract_info(filename)

        if file_id is not None and text:
            metadata_list.append({"id": file_id, "text": text, "filename": filename})
            valid_count += 1
        else:
            print(f"⚠️  跳过格式不匹配的文件: {filename} (需符合 'ID-文本.wav' 格式)")

    # 按照 id 进行排序
    metadata_list.sort(key=lambda x: x["id"])

    # 确保输出文件的目录存在
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # 写入 JSON 文件
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(metadata_list, f, ensure_ascii=False, indent=4)
        print(f"\n✅ 成功生成元数据文件: {output_file}")
        print(f"📊 共处理 {valid_count} 个音频文件。")
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")


if __name__ == "__main__":
    # 使用 argparse 处理命令行参数
    parser = argparse.ArgumentParser(
        description="扫描音频文件夹并生成 metadata JSON 文件"
    )

    # 定义参数
    parser.add_argument(
        "-i",
        "--input_dir",
        type=str,
        required=True,
        help="【必须】存放音频文件的文件夹路径",
    )
    parser.add_argument(
        "-o",
        "--output_file",
        type=str,
        required=True,
        help="【必须】生成的 JSON 文件路径",
    )

    # 解析参数
    args = parser.parse_args()

    # 执行主逻辑
    generate_metadata(args.input_dir, args.output_file)
