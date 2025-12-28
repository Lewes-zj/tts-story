"""
启动所有服务的脚本
启动统一API网关服务
"""

import subprocess
import sys
import time
import os
import argparse
import importlib.util

# 1. 定义 'indextts' 模块所在的根目录
PROJECT_ROOT = "/root/autodl-tmp/index-tts"

# 2. 检查这个路径是否已经在 Python 的搜索列表里
if PROJECT_ROOT not in sys.path:
    # 3. 如果不在，就把它添加进去
    sys.path.append(PROJECT_ROOT)
    print(f"[Info] 已将 {PROJECT_ROOT} 添加到 sys.path")  # (这行可以取消注释来调试)


def verify_index_tts2_loading():
    """验证 index-tts2 是否成功加载（使用 tts_utils）"""
    print("\n" + "=" * 60)
    print("验证 index-tts2 加载状态")
    print("=" * 60)

    # 1. 检查 index-tts 路径是否存在
    print(f"\n[1/3] 检查 index-tts 路径: {PROJECT_ROOT}")
    if os.path.exists(PROJECT_ROOT):
        print("  ✅ 路径存在")
    else:
        print("  ❌ 路径不存在！")
        print("  请确认服务器上 index-tts 的安装路径")
        return False

    # 2. 检查路径是否在 sys.path 中
    print(f"\n[2/3] 检查 sys.path")
    if PROJECT_ROOT in sys.path:
        print(f"  ✅ {PROJECT_ROOT} 已在 sys.path 中")
    else:
        print(f"  ⚠️ {PROJECT_ROOT} 不在 sys.path 中，但已通过代码添加")

    print("\n  当前 sys.path 前5个路径:")
    for i, path in enumerate(sys.path[:5], 1):
        print(f"    {i}. {path}")
    if len(sys.path) > 5:
        print(f"    ... (还有 {len(sys.path) - 5} 个路径)")

    # 3. 使用 tts_utils 验证导入
    print("\n[3/3] 使用 tts_utils 验证 IndexTTS2 导入")
    try:
        # 获取项目根目录并添加到路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        # 导入 tts_utils
        from scripts.tts_utils import TTS_AVAILABLE, IndexTTS2

        if TTS_AVAILABLE and IndexTTS2 is not None:
            print("  ✅ tts_utils 成功加载 IndexTTS2")
            print(f"  TTS_AVAILABLE = {TTS_AVAILABLE}")
            print(f"  IndexTTS2 类型: {type(IndexTTS2)}")

            # 尝试获取 indextts 模块的位置
            try:
                import indextts

                print(
                    f"  indextts 位置: {indextts.__file__ if hasattr(indextts, '__file__') else '未知'}"
                )
            except:
                pass

            print("\n" + "=" * 60)
            print("✅ index-tts2 加载验证成功！")
            print("=" * 60 + "\n")
            return True
        else:
            print("  ❌ tts_utils 未能成功加载 IndexTTS2")
            print(f"  TTS_AVAILABLE = {TTS_AVAILABLE}")
            print(f"  IndexTTS2 = {IndexTTS2}")
            print("\n  可能的原因:")
            print("    1. indextts 包未安装或路径不正确")
            print("    2. 缺少必要的依赖")
            print("    3. Python 环境不匹配")
            print(f"\n  请检查 {PROJECT_ROOT} 目录是否包含 indextts 包")
            return False

    except ImportError as e:
        print(f"  ❌ 无法导入 tts_utils: {e}")
        print("  这可能表示项目结构有问题")
        return False
    except Exception as e:
        print(f"  ❌ 验证过程中发生错误: {type(e).__name__}: {e}")
        import traceback

        print("\n  详细错误信息:")
        traceback.print_exc()
        return False


def check_and_install_dependencies():
    """检查并安装项目依赖"""
    print("检查项目依赖...")

    # 检查是否可以导入所需的模块
    required_modules = [
        ("fastapi", "fastapi>=0.68.0"),
        ("uvicorn", "uvicorn>=0.15.0"),
        ("pydantic", "pydantic>=1.8.0"),
        ("pymysql", "pymysql>=1.0.2"),
        ("yaml", "PyYAML>=6.0"),
        ("requests", "requests>=2.28.1"),
        ("multipart", "python-multipart>=0.0.5"),
        ("pydub", "pydub>=0.25.1"),
        ("torch", "torch>=1.13.0"),  # funasr的依赖
        ("torchaudio", "torchaudio"),  # funasr的依赖
        ("funasr", "funasr>=1.0.0"),  # ASR功能所需
    ]

    missing_modules = []
    for module_name, install_name in required_modules:
        try:
            importlib.util.find_spec(module_name)
        except ImportError:
            missing_modules.append((module_name, install_name))

    # 如果有缺失的模块，尝试安装它们
    if missing_modules:
        print("检测到缺失的依赖，正在自动安装...")
        try:
            import subprocess
            import sys

            # 构建安装命令
            install_cmd = [sys.executable, "-m", "pip", "install"]
            for _, install_name in missing_modules:
                install_cmd.append(install_name)

            # 执行安装
            result = subprocess.run(install_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print("依赖安装成功!")
                # 重新检查导入
                for module_name, _ in missing_modules:
                    try:
                        importlib.util.find_spec(module_name)
                    except ImportError:
                        print(f"警告: {module_name} 仍然无法导入")
            else:
                print(f"依赖安装失败: {result.stderr}")
                print(
                    "请手动安装依赖: pip install fastapi uvicorn pydantic pymysql PyYAML requests python-multipart pydub funasr"
                )
        except Exception as e:
            print(f"安装依赖时出错: {e}")
            print(
                "请手动安装依赖: pip install fastapi uvicorn pydantic pymysql PyYAML requests python-multipart pydub funasr"
            )
    else:
        print("所有依赖已安装")


def start_services(daemon=False):
    """启动统一API网关服务"""
    print("正在启动统一API网关服务...")

    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 准备环境变量（确保所有启动方式都使用相同的环境变量）
    env = os.environ.copy()
    
    # 确保PYTHONPATH包含当前目录，就像命令行中那样
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{project_root}:{current_pythonpath}"
        if current_pythonpath
        else project_root
    )
    
    # 设置 PUBLIC_BASE_URL（如果未设置，尝试从 ~/.bashrc 读取或使用默认值）
    if "PUBLIC_BASE_URL" not in env or not env["PUBLIC_BASE_URL"]:
        # 尝试从 ~/.bashrc 读取（如果用户在 shell 中设置了）
        bashrc_path = os.path.expanduser("~/.bashrc")
        if os.path.exists(bashrc_path):
            try:
                with open(bashrc_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("export PUBLIC_BASE_URL="):
                            # 提取值（处理引号）
                            value = line.split("=", 1)[1].strip()
                            # 去除引号
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            elif value.startswith("'") and value.endswith("'"):
                                value = value[1:-1]
                            if value:
                                env["PUBLIC_BASE_URL"] = value
                                print(f"从 ~/.bashrc 读取 PUBLIC_BASE_URL: {value}")
                                break
            except Exception as e:
                print(f"读取 ~/.bashrc 时出错: {e}")
        
        # 如果仍然没有设置，检查是否有 .env 文件
        if "PUBLIC_BASE_URL" not in env or not env["PUBLIC_BASE_URL"]:
            env_file = os.path.join(project_root, ".env")
            if os.path.exists(env_file):
                try:
                    with open(env_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("PUBLIC_BASE_URL="):
                                value = line.split("=", 1)[1].strip()
                                if value.startswith('"') and value.endswith('"'):
                                    value = value[1:-1]
                                elif value.startswith("'") and value.endswith("'"):
                                    value = value[1:-1]
                                if value:
                                    env["PUBLIC_BASE_URL"] = value
                                    print(f"从 .env 文件读取 PUBLIC_BASE_URL: {value}")
                                    break
                except Exception as e:
                    print(f"读取 .env 文件时出错: {e}")
        
        # 如果仍然没有设置，提示用户
        if "PUBLIC_BASE_URL" not in env or not env["PUBLIC_BASE_URL"]:
            print("⚠️  警告: PUBLIC_BASE_URL 环境变量未设置")
            print("   如果需要使用 CosyVoice V3，请设置此环境变量")
            print("   可以通过以下方式设置:")
            print("   1. 在启动前设置: export PUBLIC_BASE_URL='https://your-domain.com:8443'")
            print("   2. 创建 .env 文件: echo 'PUBLIC_BASE_URL=https://your-domain.com:8443' >> .env")
            print("   3. 在 ~/.bashrc 中添加: export PUBLIC_BASE_URL='https://your-domain.com:8443'")
    else:
        print(f"✓ PUBLIC_BASE_URL 已设置: {env['PUBLIC_BASE_URL']}")

    if daemon:
        print("以守护进程模式启动...")

        # 创建日志文件
        log_file = os.path.join(project_root, "app.log")

        # 使用 Python 运行服务
        main_api_process = subprocess.Popen(
            [
                "python3.10",
                "scripts/main_api.py",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
            cwd=project_root,
            stdout=open(log_file, "w"),
            stderr=subprocess.STDOUT,
            env=env,
        )

        print(f"服务已在后台启动，进程ID: {main_api_process.pid}")
        print(f"日志文件: {log_file}")
        print("API地址: http://localhost:8000")
        print("\n要查看日志，可以使用以下命令:")
        print(f"  tail -f {log_file}")
        print("\n要停止服务，可以使用以下命令:")
        print(f"  kill {main_api_process.pid}")
    else:
        # 使用 Python 启动统一API网关 (端口8000)
        print("启动统一API网关...")
        try:
            # 直接运行 main_api.py
            main_api_process = subprocess.Popen(
                [
                    "python3.10",
                    "scripts/main_api.py",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                ],
                cwd=project_root,
                env=env,  # 传递环境变量
            )
        except FileNotFoundError:
            # 如果没有 uv，使用传统的 Python 方式
            print("未找到 uv，使用传统 Python 方式启动...")
            main_api_process = subprocess.Popen(
                [
                    "python3.10",
                    "-m",
                    "uvicorn",
                    "scripts.main_api:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                    "--reload",
                ],
                cwd=project_root,
                env=env,  # 传递环境变量
            )

        print("统一API网关已启动:")
        print("- 主API: http://localhost:8000")
        print("- 统一API文档: http://localhost:8000/docs")
        print("- API Redoc文档: http://localhost:8000/redoc")
        print("- 情绪向量处理API: http://localhost:8000/emo_vector")
        print("- 文件上传API: http://localhost:8000/file")
        print("- 有声故事书API: http://localhost:8000/story_book")
        print("- 按 Ctrl+C 停止服务")

        try:
            # 等待进程完成
            main_api_process.wait()
        except KeyboardInterrupt:
            print("\n正在停止服务...")
            main_api_process.terminate()
            main_api_process.wait()
            print("服务已停止")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="启动TTS统一API服务")
    parser.add_argument(
        "-d", "--daemon", action="store_true", help="以守护进程模式运行"
    )
    args = parser.parse_args()

    # 检查并安装依赖
    check_and_install_dependencies()

    # 验证 index-tts2 加载
    if not verify_index_tts2_loading():
        print("\n❌ index-tts2 加载验证失败！")
        print("请检查以下事项:")
        print(f"  1. 确认 index-tts 已安装在: {PROJECT_ROOT}")
        print(f"  2. 确认路径配置正确")
        print(f"  3. 确认 Python 环境正确")
        print("\n是否继续启动服务？(y/n): ", end="")

        # 在守护进程模式下自动继续
        if args.daemon:
            print("守护进程模式，自动继续...")
        else:
            user_input = input().strip().lower()
            if user_input != "y":
                print("已取消启动")
                sys.exit(1)

    start_services(daemon=args.daemon)
