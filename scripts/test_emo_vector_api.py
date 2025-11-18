"""
测试情绪向量API
"""

import sys
import os
import requests
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_emo_vector_api():
    """测试情绪向量API"""
    # API地址
    url = "http://localhost:8000/process_emo_vector/"

    # 测试数据
    data = {
        "user_id": 1,
        "role_id": 1,
        "clean_input_audio": "/path/to/input/audio.wav",
        "text": "这是一个测试文本",
    }

    # 发送POST请求
    try:
        response = requests.post(url, json=data)
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {response.json()}")
    except Exception as e:
        print(f"请求过程中发生错误: {e}")


if __name__ == "__main__":
    test_emo_vector_api()

