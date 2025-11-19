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
        ("pydub", "pydub>=0.25.1")
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
                print("请手动安装依赖: pip install fastapi uvicorn pydantic pymysql PyYAML requests python-multipart pydub")
        except Exception as e:
            print(f"安装依赖时出错: {e}")
            print("请手动安装依赖: pip install fastapi uvicorn pydantic pymysql PyYAML requests python-multipart pydub")
    else:
        print("所有依赖已安装")


def start_services(daemon=False):
    """启动统一API网关服务"""
    print("正在启动统一API网关服务...")

    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if daemon:
        print("以守护进程模式启动...")
        # 以守护进程模式启动，设置工作目录和环境变量
        env = os.environ.copy()
        # 确保PYTHONPATH包含当前目录，就像命令行中那样
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{project_root}:{current_pythonpath}"
            if current_pythonpath
            else project_root
        )

        # 创建日志文件
        log_file = os.path.join(project_root, "app.log")

        # 使用 uv 运行服务
        main_api_process = subprocess.Popen(
            ["python3.10", "scripts/main_api.py", "--host", "0.0.0.0", "--port", "8000", "scripts/main_api.py"],
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
        # 使用 uv 启动统一API网关 (端口8000)
        print("使用 uv 启动统一API网关...")
        try:
            # 尝试使用 uv 运行
            main_api_process = subprocess.Popen(
                ["python3.10", "scripts/main_api.py", "--host", "0.0.0.0", "--port", "8000", "scripts/main_api.py"], cwd=project_root
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
    
    start_services(daemon=args.daemon)
