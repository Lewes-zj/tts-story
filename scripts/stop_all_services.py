"""
停止所有服务的脚本
"""

import subprocess
import sys
import os
import signal

def stop_services():
    """停止所有服务"""
    print("正在停止所有服务...")
    
    # 方法1: 使用pkill停止相关进程
    try:
        subprocess.run(["pkill", "-f", "main_api.py"], check=True)
        print("已停止 main_api.py 进程")
    except subprocess.CalledProcessError:
        print("未找到 main_api.py 进程")
    
    try:
        subprocess.run(["pkill", "-f", "start_all_services"], check=True)
        print("已停止 start_all_services 进程")
    except subprocess.CalledProcessError:
        print("未找到 start_all_services 进程")
    
    # 方法2: 查找并停止占用8000端口的进程
    try:
        result = subprocess.run(["lsof", "-i", ":8000"], capture_output=True, text=True)
        if result.stdout:
            lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
            for line in lines:
                parts = line.split()
                if len(parts) > 1:
                    pid = parts[1]
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        print(f"已停止端口8000上的进程 (PID: {pid})")
                    except ProcessLookupError:
                        print(f"进程 {pid} 已经不存在")
                    except PermissionError:
                        print(f"没有权限终止进程 {pid}")
        else:
            print("未找到占用端口8000的进程")
    except FileNotFoundError:
        print("未找到 lsof 命令，跳过端口检查")

if __name__ == "__main__":
    stop_services()