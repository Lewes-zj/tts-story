"""
文件上传API
使用FastAPI封装文件上传功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
import os
import shutil
from typing import List, Optional

# 导入文件上传器
from scripts.file_uploader import FileUploader

# 创建FastAPI应用实例
app = FastAPI(title="文件上传API", description="提供文件上传到指定文件夹的功能")

# 创建文件上传器实例，使用项目根目录下的uploads目录
file_uploader = FileUploader("uploads")


@app.post("/upload/", summary="上传单个文件")
async def upload_file(
    file: UploadFile = File(...), target_folder: Optional[str] = Form(None)
):
    """
    上传单个文件到指定文件夹

    Args:
        file (UploadFile): 要上传的文件
        target_folder (str, optional): 目标文件夹名称，默认为None表示直接放在基础目录下

    Returns:
        dict: 上传结果信息
    """
    try:
        # 创建临时文件路径
        temp_file_path = f"temp_{file.filename}"

        # 保存上传的文件到临时位置
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 使用文件上传器上传文件
        uploaded_file_path = file_uploader.upload_file(temp_file_path, target_folder)

        # 删除临时文件
        os.remove(temp_file_path)

        return {
            "filename": file.filename,
            "uploaded_path": uploaded_file_path,
            "message": "文件上传成功",
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@app.post("/upload/multiple/", summary="批量上传文件")
async def upload_multiple_files(
    files: List[UploadFile] = File(...), target_folder: Optional[str] = Form(None)
):
    """
    批量上传文件到指定文件夹

    Args:
        files (List[UploadFile]): 要上传的文件列表
        target_folder (str, optional): 目标文件夹名称，默认为None表示直接放在基础目录下

    Returns:
        dict: 上传结果信息
    """
    try:
        # 保存上传的文件到临时位置
        temp_file_paths = []
        for file in files:
            temp_file_path = f"temp_{file.filename}"
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            temp_file_paths.append(temp_file_path)

        # 使用文件上传器批量上传文件
        uploaded_file_paths = file_uploader.upload_files(temp_file_paths, target_folder)

        # 删除临时文件
        for temp_file_path in temp_file_paths:
            os.remove(temp_file_path)

        return {
            "uploaded_files": uploaded_file_paths,
            "message": f"成功上传 {len(uploaded_file_paths)} 个文件",
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@app.get("/files/", summary="列出已上传的文件")
async def list_files(folder: Optional[str] = None):
    """
    列出已上传的文件

    Args:
        folder (str, optional): 特定文件夹名称，默认为None表示列出基础目录下的所有文件

    Returns:
        dict: 文件列表
    """
    try:
        file_list = file_uploader.list_uploaded_files(folder)
        return {"files": file_list, "count": len(file_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@app.get("/", summary="API根路径")
async def root():
    """
    API根路径

    Returns:
        dict: 欢迎信息
    """
    return {"message": "欢迎使用文件上传API", "version": "1.0.0"}


# 如果直接运行此文件，则启动服务器

