"""
使用示例：如何导入和使用 cosyvoice_v3 模块
"""
import os
import sys

# 如果脚本在其他目录，需要添加脚本目录到路径
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 方式1: 从同一目录导入
from cosyvoice_v3 import CosyVoiceV3


def example_basic_usage():
    """基本使用示例"""
    print("=== 基本使用示例 ===")
    
    # 创建客户端实例（API key 从环境变量 DASHSCOPE_API_KEY 读取）
    client = CosyVoiceV3()
    
    # 定义参数
    audio_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/cosyvoice/cosyvoice-zeroshot-sample.wav"
    text_to_synthesize = "小朋友们大家好，这是一段测试音频"
    
    # 调用合成方法
    audio_data = client.synthesize(
        audio_url=audio_url,
        text_to_synthesize=text_to_synthesize,
        output_file="outputs/example_output.mp3"
    )
    
    print(f"合成成功！音频数据大小: {len(audio_data)} 字节")


def example_with_api_key():
    """使用 API Key 参数示例"""
    print("\n=== 使用 API Key 参数示例 ===")
    
    # 直接在初始化时传入 API Key
    api_key = "sk-your-api-key-here"  # 替换为你的 API Key
    client = CosyVoiceV3(api_key=api_key)
    
    audio_url = "https://your-audio-url.com/sample.wav"
    text = "这是使用自定义 API Key 的示例"
    
    audio_data = client.synthesize(
        audio_url=audio_url,
        text_to_synthesize=text
    )
    
    # 手动保存音频数据
    with open("outputs/manual_save.mp3", "wb") as f:
        f.write(audio_data)
    print("音频已保存")


def example_with_custom_config():
    """使用自定义配置示例"""
    print("\n=== 使用自定义配置示例 ===")
    
    # 自定义配置参数
    client = CosyVoiceV3(
        target_model="cosyvoice-v3-plus",
        voice_prefix="myvoice",  # 自定义音色前缀
        max_attempts=60,  # 增加轮询次数
        poll_interval=5   # 减少轮询间隔
    )
    
    audio_url = "https://your-audio-url.com/sample.wav"
    text = "这是使用自定义配置的示例"
    
    audio_data = client.synthesize(
        audio_url=audio_url,
        text_to_synthesize=text,
        output_file="outputs/custom_config_output.mp3"
    )


def example_only_return_data():
    """只返回音频数据，不保存文件示例"""
    print("\n=== 只返回音频数据示例 ===")
    
    client = CosyVoiceV3()
    
    audio_url = "https://your-audio-url.com/sample.wav"
    text = "这段音频将只返回数据，不保存文件"
    
    # 不传入 output_file 参数
    audio_data = client.synthesize(
        audio_url=audio_url,
        text_to_synthesize=text
    )
    
    # 可以后续处理音频数据
    print(f"获取到音频数据: {len(audio_data)} 字节")
    # 可以上传到云存储、发送给客户端等
    # upload_to_cloud_storage(audio_data)


def example_from_other_directory():
    """从其他目录导入的示例"""
    print("\n=== 从其他目录导入示例 ===")
    
    # 如果从其他目录导入，需要添加路径
    # import sys
    # script_dir = "/path/to/scripts"
    # if script_dir not in sys.path:
    #     sys.path.insert(0, script_dir)
    # from cosyvoice_v3 import CosyVoiceV3
    
    # 或者使用相对导入（如果在包结构中）
    # from scripts.cosyvoice_v3 import CosyVoiceV3
    
    pass


if __name__ == "__main__":
    # 运行示例（注释掉不需要的示例）
    
    # 基本使用
    # example_basic_usage()
    
    # 使用 API Key
    # example_with_api_key()
    
    # 自定义配置
    # example_with_custom_config()
    
    # 只返回数据
    # example_only_return_data()
    
    print("请取消注释相应的示例函数来运行")

