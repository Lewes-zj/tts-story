"""
有声故事书生成功能使用示例
演示如何使用有声故事书生成功能
"""

import requests
import json

def example_story_book_generation():
    """有声故事书生成示例"""
    # API端点
    api_url = "http://localhost:8000/story_book/generate"
    
    # 请求数据
    payload = {
        "user_id": 1,
        "role_id": 1,
        "story_path": "db/xiaohongmao.json"
    }
    
    # 发送POST请求
    try:
        response = requests.post(api_url, json=payload)
        
        # 检查响应状态
        if response.status_code == 200:
            result = response.json()
            print("有声故事书生成结果:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
            if result.get("success"):
                print(f"成功生成有声故事书: {result.get('story_book_path')}")
            else:
                print(f"生成失败: {result.get('message')}")
        else:
            print(f"请求失败，状态码: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"请求出错: {str(e)}")
    except Exception as e:
        print(f"处理响应时出错: {str(e)}")

if __name__ == "__main__":
    print("有声故事书生成功能使用示例")
    print("=" * 40)
    example_story_book_generation()
    