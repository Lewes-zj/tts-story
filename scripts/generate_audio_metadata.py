#!/usr/bin/env python3
"""
生成音频文件元数据JSON
从指定目录读取音频文件，解析文件名，生成包含排序、文本和文件名的JSON文件
"""

import os
import re
import json
from pathlib import Path


def parse_audio_filename(filename):
    """
    解析音频文件名

    格式示例:
    - 01-今年伦敦的春天似乎比往年来得早些.WAV
    - 17-STF-华生先生你怎么在这里啊.WAV
    - 21-啊原来是你啊.mp3

    Args:
        filename: 文件名

    Returns:
        tuple: (序号, 文本内容) 或 None
    """
    # 匹配格式: 序号-[角色名-]文本内容.扩展名
    # 支持 01、001 等带前导0的序号
    pattern = r"^(\d+)-([\w-]*?-)?(.+)\.(WAV|wav|mp3|MP3)$"
    match = re.match(pattern, filename)

    if match:
        sort_num = int(match.group(1))  # 自动去掉前导0
        text_content = match.group(3)  # 文本内容
        return sort_num, text_content

    return None


def generate_audio_metadata(directory_path, output_path=None):
    """
    生成音频文件元数据JSON

    Args:
        directory_path: 音频文件目录路径
        output_path: 输出JSON文件路径，默认为当前目录下的 audio_metadata.json
    """
    if not os.path.exists(directory_path):
        print(f"错误：目录不存在 - {directory_path}")
        return

    # 默认输出路径
    if output_path is None:
        output_path = "audio_metadata.json"

    # 扫描目录
    audio_files = []
    supported_extensions = (".wav", ".WAV", ".mp3", ".MP3", ".flac", ".FLAC")

    for filename in os.listdir(directory_path):
        if not filename.endswith(supported_extensions):
            continue

        result = parse_audio_filename(filename)
        if result:
            sort_num, text_content = result
            audio_files.append(
                {"sort": sort_num, "text": text_content, "emo_audio": filename}
            )
        else:
            print(f"警告：无法解析文件名 - {filename}")

    # 按序号排序
    audio_files.sort(key=lambda x: x["sort"])

    # 生成JSON文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(audio_files, f, ensure_ascii=False, indent=2)

    print(f"✅ 成功生成元数据文件: {output_path}")
    print(f"   共处理 {len(audio_files)} 个音频文件")

    # 显示前几条预览
    print("\n前5条预览:")
    for item in audio_files[:5]:
        print(f"  {item['sort']:3d}. {item['text'][:30]}...")

    return audio_files


if __name__ == "__main__":
    import sys

    # 使用命令行参数或默认路径
    if len(sys.argv) > 1:
        audio_dir = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else "audio_metadata.json"
    else:
        # 默认路径
        audio_dir = "/Users/xinliu/Documents/xxx/story-project/role_audio/福尔摩斯第一集原人声切片/旁白"
        output_file = "/Users/xinliu/Documents/xxx/story-project/tts-story/db/sherlock_holmes_narrator_01.json"

    print("=" * 60)
    print("音频文件元数据生成工具")
    print("=" * 60)
    print(f"读取目录: {audio_dir}")
    print(f"输出文件: {output_file}")
    print("=" * 60)

    generate_audio_metadata(audio_dir, output_file)

    print("\n完成！")
