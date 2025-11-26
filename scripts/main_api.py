import sys

sys.path.append("/root/autodl-tmp/index-tts")
"""
统一API网关
将所有API服务整合到一个应用中，提供统一的API文档
"""

import sys
import os

# 添加项目根目录到Python路径，确保能正确导入模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

# 确保PYTHONPATH包含当前目录
current_pythonpath = os.environ.get("PYTHONPATH", "")
if project_root not in current_pythonpath:
    os.environ["PYTHONPATH"] = (
        f"{project_root}:{current_pythonpath}" if current_pythonpath else project_root
    )

# 创建主应用
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="TTS统一API服务", description="整合所有TTS相关服务的统一API网关")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入路由
# 情绪向量处理API路由
from scripts.emo_vector_api import router as emo_vector_router

# 文件上传API路由
from scripts.file_upload_api import upload_file as file_upload_file
from scripts.file_upload_api import upload_multiple_files as file_upload_multiple_files
from scripts.file_upload_api import list_files as file_list_files
from scripts.file_upload_api import root as file_root

# 有声故事书API路由
STORY_BOOK_API_AVAILABLE = False
try:
    from scripts.story_book_api import StoryBookRequest, StoryBookResponse
    from scripts.story_book_api import (
        generate_story_book as story_book_generate_story_book,
    )
    from scripts.story_book_api import root as story_book_root

    STORY_BOOK_API_AVAILABLE = True
except ImportError:
    print("警告: 无法导入有声故事书API，该功能将不可用")
    # 定义默认值以避免变量未绑定错误
    StoryBookRequest = None
    StoryBookResponse = None
    story_book_generate_story_book = None
    story_book_root = None

# 添加情绪向量处理API路由
app.include_router(emo_vector_router)

# 添加文件上传API路由
app.post("/file/upload/", summary="上传单个文件")(file_upload_file)
app.post("/file/upload/multiple/", summary="批量上传文件")(file_upload_multiple_files)
app.get("/file/files/", summary="列出已上传的文件")(file_list_files)
app.get("/file/", summary="文件上传API根路径")(file_root)

# 添加有声故事书API路由
if (
    STORY_BOOK_API_AVAILABLE
    and story_book_generate_story_book is not None
    and story_book_root is not None
):
    app.post(
        "/story_book/generate/",
        response_model=StoryBookResponse,
        summary="生成有声故事书",
    )(story_book_generate_story_book)
    app.get("/story_book/", summary="有声故事书API根路径")(story_book_root)
else:
    print("有声故事书API不可用，跳过路由注册")

# 添加新的API路由（用户管理、角色管理、故事管理、任务管理、文件管理）
try:
    from scripts.auth_api import router as auth_router
    from scripts.character_api import router as character_router
    from scripts.story_api import router as story_router
    from scripts.task_api import router as task_router
    from scripts.file_api import router as file_router
    from scripts.user_story_book_api import router as user_story_book_router

    app.include_router(auth_router)
    app.include_router(character_router)
    app.include_router(story_router)
    app.include_router(task_router)
    app.include_router(file_router)
    app.include_router(user_story_book_router)
    print("✓ 新的API路由已成功注册")
    print("  - 认证API: /api/auth")
    print("  - 角色管理API: /api/characters")
    print("  - 故事管理API: /api/stories")
    print("  - 任务管理API: /api/tasks")
    print("  - 文件管理API: /api/files")
    print("  - 用户有声故事书API: /api/user_story_books")

except ImportError as e:
    import traceback
    print(f"✗ 警告: 无法导入新的API路由，部分功能将不可用")
    print(f"错误详情: {str(e)}")
    traceback.print_exc()
except Exception as e:
    import traceback
    print(f"✗ 错误: 注册新的API路由时发生异常")
    print(f"错误详情: {str(e)}")
    traceback.print_exc()


@app.get("/", summary="API根路径")
async def root():
    """
    API根路径

    Returns:
        dict: 欢迎信息和API使用说明
    """
    return {
        "message": "欢迎使用TTS统一API服务",
        "version": "1.0.0",
        "docs": {"统一API文档": "/docs", "API Redoc文档": "/redoc"},
    }


# 打印所有已注册的路由（用于调试）
def print_routes():
    """打印所有已注册的路由"""
    print("\n=== 已注册的API路由 ===")
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            methods = ", ".join(route.methods) if route.methods else "GET"
            print(f"{methods:8} {route.path}")
    print("=" * 50 + "\n")

# 如果直接运行此文件，则启动服务器
if __name__ == "__main__":
    # 打印所有路由用于调试
    print_routes()
    uvicorn.run(app, host="0.0.0.0", port=8000)
