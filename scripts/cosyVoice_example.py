"""
CosyVoice 声音复刻 API 调用示例

本文件展示了如何使用 CosyVoiceService 进行声音复刻和语音合成。

使用方法:
1. 在下面的配置区域设置 DASHSCOPE_API_KEY（或使用环境变量）
2. 运行示例: python scripts/cosyVoice_example.py
"""

import os
import sys
import http.server
import socketserver
import threading
import time
from typing import Optional
from urllib.parse import urlparse

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.cosyVoice import CosyVoiceService, TargetModel  # noqa: E402

# ==================== 配置区域 ====================
# 在这里设置你的 DashScope API Key
# 方式1: 直接在代码中设置（推荐用于测试）
DASHSCOPE_API_KEY = "sk-d9c9aaa532a44f629758294cd17ecde1"  # 请替换为你的实际 API Key

# 方式2: 从环境变量读取（推荐用于生产环境）
# 如果上面的 API_KEY 是占位符（未设置），则尝试从环境变量读取
# 注意：如果你已经在上面设置了实际的 API_KEY，下面的代码不会执行
_DEFAULT_PLACEHOLDER = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # 默认占位符
if DASHSCOPE_API_KEY == _DEFAULT_PLACEHOLDER:
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# ngrok 配置（如果使用 ngrok 暴露本地服务）
# 如果设置了 ngrok URL，本地文件 URL 会自动替换为 ngrok URL
NGROK_URL = "https://gertrude-unsustaining-derisively.ngrok-free.dev"  # 你的 ngrok URL，如果不需要可以设为 None
# ==================================================


def get_local_file_url(local_path: str, port: int = 8001) -> str:
    """
    将本地文件路径转换为可访问的 URL（通过启动临时 HTTP 服务器）
    
    注意：这个方法仅用于开发和测试。生产环境请将文件上传到 OSS 等公网存储。
    
    Args:
        local_path: 本地文件路径
        port: HTTP 服务器端口（默认 8001）
    
    Returns:
        str: 可访问的 URL
    
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 路径无效
    """
    local_path = os.path.abspath(local_path)
    
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"文件不存在: {local_path}")
    
    if not os.path.isfile(local_path):
        raise ValueError(f"路径不是文件: {local_path}")
    
    # 获取文件的绝对路径和目录
    file_dir = os.path.dirname(local_path)
    file_name = os.path.basename(local_path)
    
    # 创建自定义的 HTTP 请求处理器
    class FileHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=file_dir, **kwargs)
        
        def log_message(self, format, *args):
            # 减少日志输出
            pass
    
    # 检查端口是否已被占用
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    
    if result == 0:
        # 端口已被占用，假设服务器已启动
        print(f"⚠️  端口 {port} 已被占用，假设 HTTP 服务器已运行")
        return f"http://127.0.0.1:{port}/{file_name}"
    
    # 启动 HTTP 服务器（在后台线程中）
    def start_server():
        with socketserver.TCPServer(("", port), FileHandler) as httpd:
            httpd.serve_forever()
    
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 等待服务器启动
    time.sleep(1)
    
    # 构建 URL
    # 注意：这里返回的是 localhost URL，如果 CosyVoice API 需要公网可访问的 URL
    # 你需要使用 ngrok 或其他工具将 localhost 暴露到公网
    url = f"http://127.0.0.1:{port}/{file_name}"
    
    print(f"📡 已启动临时 HTTP 服务器 (端口 {port})")
    print(f"   ⚠️  注意: 如果 CosyVoice API 无法访问 localhost，请使用 ngrok 等工具")
    print(f"   💡 提示: ngrok http {port} 可以将本地服务暴露到公网")
    
    return url


def prepare_audio_url(audio_input: str, ngrok_url: Optional[str] = None) -> str:
    """
    准备音频 URL，支持本地文件路径和 HTTP URL
    
    Args:
        audio_input: 本地文件路径或 HTTP URL
        ngrok_url: ngrok 公网 URL（如果设置了，会将 localhost URL 替换为 ngrok URL）
    
    Returns:
        str: 可用的音频 URL
    
    Raises:
        FileNotFoundError: 本地文件不存在
        ValueError: 输入无效
    """
    # 检查是否是 URL
    parsed = urlparse(audio_input)
    if parsed.scheme in ('http', 'https'):
        # 已经是 URL
        return audio_input
    
    # 是本地路径，转换为 URL
    if not os.path.exists(audio_input):
        raise FileNotFoundError(f"音频文件不存在: {audio_input}")
    
    # 使用临时 HTTP 服务器提供文件访问
    local_url = get_local_file_url(audio_input)
    
    # 如果设置了 ngrok URL，替换 localhost 为 ngrok URL
    if ngrok_url:
        # 从 localhost URL 中提取路径部分
        file_name = os.path.basename(audio_input)
        ngrok_audio_url = f"{ngrok_url.rstrip('/')}/{file_name}"
        print(f"   🔗 使用 ngrok URL: {ngrok_audio_url}")
        return ngrok_audio_url
    
    return local_url


def example_1_basic_usage():
    """示例1: 基本使用流程 - 从创建音色到语音合成"""
    print("\n" + "=" * 60)
    print("示例1: 基本使用流程")
    print("=" * 60)
    
    # 1. 初始化服务（使用配置的 API Key）
    try:
        service = CosyVoiceService(api_key=DASHSCOPE_API_KEY)
        print("✅ CosyVoice 服务初始化成功")
    except ValueError as e:
        print(f"❌ 初始化失败: {e}")
        print("提示: 请在代码开头设置 DASHSCOPE_API_KEY，或设置环境变量 DASHSCOPE_API_KEY")
        return
    
    # 2. 创建音色（支持本地文件路径或公网可访问的音频 URL）
    # 方式1: 使用本地文件路径（请修改为你的实际音频文件路径）
    audio_path = "/Users/xinliu/Documents/xxx/story-project/role_audio/1766733909618_clean.wav"  # 本地文件路径示例
    # 方式2: 使用公网 URL（推荐生产环境使用）
    # audio_path = "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/cosyvoice/cosyvoice-zeroshot-sample.wav"
    
    print(f"\n📝 开始创建音色...")
    print(f"   音频输入: {audio_path}")
    
    # 检查是否是本地文件
    if os.path.exists(audio_path) and os.path.isfile(audio_path):
        # 本地文件，需要转换为可访问的 URL
        print(f"   📁 检测到本地文件，正在准备可访问的 URL...")
        try:
            audio_url = prepare_audio_url(audio_path, ngrok_url=NGROK_URL)
            print(f"   ✅ 音频 URL: {audio_url}")
        except Exception as e:
            print(f"❌ 准备音频 URL 失败: {e}")
            return
    else:
        # 假设是 URL 或提示用户
        if audio_path.startswith(('http://', 'https://')):
            audio_url = audio_path
            print(f"   ✅ 使用公网 URL: {audio_url}")
        else:
            print(f"❌ 文件不存在: {audio_path}")
            print("💡 提示: 请修改 audio_path 变量为实际的音频文件路径或公网 URL")
            return
    
    try:
        # 如果遇到超时问题，可以设置 wait_for_completion=False，然后手动查询状态
        voice_info = service.create_voice(
            target_model=TargetModel.COSYVOICE_V3_PLUS.value,
            prefix="demovoice",  # 必须小于10个字符
            audio_url=audio_url,
            description="示例音色 - 用于演示",
            wait_for_completion=True,  # 如果经常超时，可以改为 False
            timeout=600  # 增加超时时间到10分钟
        )
        print(f"✅ 音色创建成功!")
        print(f"   Voice ID: {voice_info.voice_id}")
        print(f"   状态: {voice_info.status}")
        
        # 3. 使用音色进行语音合成
        print(f"\n🎤 开始语音合成...")
        output_path = "output_demo.wav"
        service.synthesize_speech_to_file(
            text="小朋友们大家好，这是一段黄金母本的音频，这段音频的主要目的呀，是为后续的所有音频克隆提供一段完美的音频输入",
            output_path=output_path,
            voice_id=voice_info.voice_id
        )
        print(f"✅ 语音合成完成!")
        print(f"   输出文件: {output_path}")
        
    except Exception as e:
        print(f"❌ 操作失败: {e}")


def example_2_list_voices():
    """示例2: 查询和管理音色列表"""
    print("\n" + "=" * 60)
    print("示例2: 查询音色列表")
    print("=" * 60)
    
    try:
        service = CosyVoiceService(api_key=DASHSCOPE_API_KEY)
        
        # 查询所有音色
        print("\n📋 查询所有音色...")
        all_voices = service.list_voices()
        print(f"   共有 {len(all_voices)} 个音色")
        
        # 按模型筛选
        print("\n📋 查询 cosyvoice-v3-plus 模型的音色...")
        v3_voices = service.list_voices(target_model=TargetModel.COSYVOICE_V3_PLUS.value)
        print(f"   共有 {len(v3_voices)} 个音色")
        
        # 显示音色详情
        if v3_voices:
            print("\n📝 音色列表:")
            for i, voice in enumerate(v3_voices[:5], 1):  # 只显示前5个
                print(f"   {i}. {voice.voice_id}")
                print(f"      前缀: {voice.prefix}")
                print(f"      状态: {voice.status}")
                print(f"      模型: {voice.target_model}")
                if voice.description:
                    print(f"      描述: {voice.description}")
                print()
        
    except Exception as e:
        print(f"❌ 查询失败: {e}")


def example_3_get_voice_detail():
    """示例3: 查询音色详情"""
    print("\n" + "=" * 60)
    print("示例3: 查询音色详情")
    print("=" * 60)
    
    try:
        service = CosyVoiceService(api_key=DASHSCOPE_API_KEY)
        
        # 先获取一个音色 ID（如果有的话）
        voices = service.list_voices()
        if not voices:
            print("❌ 没有可用的音色，请先创建音色")
            return
        
        voice_id = voices[0].voice_id
        print(f"\n🔍 查询音色详情: {voice_id}")
        
        voice_detail = service.get_voice(voice_id)
        print(f"✅ 音色详情:")
        print(f"   Voice ID: {voice_detail.voice_id}")
        print(f"   前缀: {voice_detail.prefix}")
        print(f"   模型: {voice_detail.target_model}")
        print(f"   状态: {voice_detail.status}")
        if voice_detail.description:
            print(f"   描述: {voice_detail.description}")
        if voice_detail.created_at:
            print(f"   创建时间: {voice_detail.created_at}")
        if voice_detail.updated_at:
            print(f"   更新时间: {voice_detail.updated_at}")
        
    except Exception as e:
        print(f"❌ 查询失败: {e}")


def example_4_synthesis_with_params():
    """示例4: 使用不同参数进行语音合成"""
    print("\n" + "=" * 60)
    print("示例4: 使用不同参数进行语音合成")
    print("=" * 60)
    
    try:
        service = CosyVoiceService(api_key=DASHSCOPE_API_KEY)
        
        # 获取一个可用的音色
        voices = service.list_voices()
        if not voices:
            print("❌ 没有可用的音色，请先创建音色")
            return
        
        voice_id = voices[0].voice_id
        text = "这是测试不同语速和音量的语音合成效果。"
        
        # 正常语速和音量
        print("\n🎤 正常语速和音量...")
        service.synthesize_speech_to_file(
            text=text,
            output_path="output_normal.wav",
            voice_id=voice_id,
            speech_rate=1.0,
            volume=1.0
        )
        print("   ✅ 已保存: output_normal.wav")
        
        # 慢速
        print("\n🎤 慢速 (0.7)...")
        service.synthesize_speech_to_file(
            text=text,
            output_path="output_slow.wav",
            voice_id=voice_id,
            speech_rate=0.7,
            volume=1.0
        )
        print("   ✅ 已保存: output_slow.wav")
        
        # 快速
        print("\n🎤 快速 (1.5)...")
        service.synthesize_speech_to_file(
            text=text,
            output_path="output_fast.wav",
            voice_id=voice_id,
            speech_rate=1.5,
            volume=1.0
        )
        print("   ✅ 已保存: output_fast.wav")
        
        # 低音量
        print("\n🎤 低音量 (0.5)...")
        service.synthesize_speech_to_file(
            text=text,
            output_path="output_low_volume.wav",
            voice_id=voice_id,
            speech_rate=1.0,
            volume=0.5
        )
        print("   ✅ 已保存: output_low_volume.wav")
        
    except Exception as e:
        print(f"❌ 合成失败: {e}")


def example_5_update_voice():
    """示例5: 更新音色信息"""
    print("\n" + "=" * 60)
    print("示例5: 更新音色信息")
    print("=" * 60)
    
    try:
        service = CosyVoiceService(api_key=DASHSCOPE_API_KEY)
        
        # 获取一个可用的音色
        voices = service.list_voices()
        if not voices:
            print("❌ 没有可用的音色，请先创建音色")
            return
        
        voice_id = voices[0].voice_id
        print(f"\n📝 更新音色: {voice_id}")
        
        # 更新描述
        updated_voice = service.update_voice(
            voice_id=voice_id,
            description="更新后的描述 - 这是一个测试音色"
        )
        print(f"✅ 音色更新成功!")
        print(f"   新描述: {updated_voice.description}")
        
    except Exception as e:
        print(f"❌ 更新失败: {e}")


def example_6_create_voice_without_wait():
    """示例6: 创建音色但不等待完成（异步方式）"""
    print("\n" + "=" * 60)
    print("示例6: 异步创建音色")
    print("=" * 60)
    
    try:
        service = CosyVoiceService(api_key=DASHSCOPE_API_KEY)
        
        audio_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/cosyvoice/cosyvoice-zeroshot-sample.wav"
        print(f"\n📝 异步创建音色（不等待完成）...")
        
        voice_info = service.create_voice(
            target_model=TargetModel.COSYVOICE_V3_PLUS.value,
            prefix="asyncdemo",  # 必须小于10个字符
            audio_url=audio_url,
            wait_for_completion=False  # 不等待完成
        )
        
        print(f"✅ 音色创建请求已提交!")
        print(f"   Voice ID: {voice_info.voice_id}")
        print(f"   状态: {voice_info.status}")
        print(f"\n💡 提示: 可以稍后使用 get_voice() 查询创建状态")
        
        # 手动查询状态
        import time
        print(f"\n⏳ 等待5秒后查询状态...")
        time.sleep(5)
        
        updated_info = service.get_voice(voice_info.voice_id)
        print(f"   当前状态: {updated_info.status}")
        
    except Exception as e:
        print(f"❌ 操作失败: {e}")


def example_7_use_existing_voice():
    """示例7: 使用已存在的音色进行合成（不需要创建新音色）"""
    print("\n" + "=" * 60)
    print("示例7: 使用已存在的音色")
    print("=" * 60)
    
    try:
        service = CosyVoiceService(api_key=DASHSCOPE_API_KEY)
        
        # 查询现有音色
        voices = service.list_voices()
        if not voices:
            print("❌ 没有可用的音色")
            print("💡 提示: 请先运行示例1创建音色，或使用已有的音色 ID")
            return
        
        # 使用第一个音色
        voice = voices[0]
        print(f"\n🎤 使用音色: {voice.voice_id}")
        print(f"   模型: {voice.target_model}")
        print(f"   状态: {voice.status}")
        
        if voice.status != "ready":
            print(f"⚠️  警告: 音色状态为 {voice.status}，可能无法使用")
        
        # 进行语音合成
        text = "这是使用已存在音色进行的语音合成测试。"
        output_path = "output_existing_voice.wav"
        
        service.synthesize_speech_to_file(
            text=text,
            output_path=output_path,
            voice_id=voice.voice_id
        )
        
        print(f"✅ 语音合成完成!")
        print(f"   输出文件: {output_path}")
        
    except Exception as e:
        print(f"❌ 操作失败: {e}")


def main():
    """主函数 - 运行所有示例"""
    print("\n" + "=" * 60)
    print("CosyVoice 声音复刻 API 调用示例")
    print("=" * 60)
    print("\n请选择要运行的示例:")
    print("1. 基本使用流程（创建音色 + 语音合成）")
    print("2. 查询音色列表")
    print("3. 查询音色详情")
    print("4. 使用不同参数进行语音合成")
    print("5. 更新音色信息")
    print("6. 异步创建音色")
    print("7. 使用已存在的音色")
    print("0. 运行所有示例")
    print("\n提示: 首次使用请先运行示例1创建音色")
    
    choice = input("\n请输入选项 (0-7): ").strip()
    
    examples = {
        "1": example_1_basic_usage,
        "2": example_2_list_voices,
        "3": example_3_get_voice_detail,
        "4": example_4_synthesis_with_params,
        "5": example_5_update_voice,
        "6": example_6_create_voice_without_wait,
        "7": example_7_use_existing_voice,
    }
    
    if choice == "0":
        # 运行所有示例
        for func in examples.values():
            try:
                func()
            except KeyboardInterrupt:
                print("\n\n⚠️  用户中断")
                break
            except Exception as e:
                print(f"\n❌ 示例执行失败: {e}")
                continue
    elif choice in examples:
        try:
            examples[choice]()
        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断")
        except Exception as e:
            print(f"\n❌ 示例执行失败: {e}")
    else:
        print("❌ 无效的选项")


if __name__ == "__main__":
    main()

