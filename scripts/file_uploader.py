"""
文件上传工具类
提供上传文件到指定文件夹的功能
"""

import os
import shutil
from typing import List, Optional


class FileUploader:
    """文件上传器类"""

    def __init__(self, upload_base_dir: str = "uploads"):
        """
        初始化文件上传器

        Args:
            upload_base_dir (str): 上传文件的基础目录，默认为 "uploads"
        """
        # 使用项目根目录下的uploads目录
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.upload_base_dir = os.path.join(self.project_root, upload_base_dir)
        # 确保基础目录存在
        os.makedirs(self.upload_base_dir, exist_ok=True)

    def upload_file(
        self, source_file_path: str, target_folder: Optional[str] = None
    ) -> str:
        """
        上传单个文件到指定文件夹

        Args:
            source_file_path (str): 源文件路径
            target_folder (str, optional): 目标文件夹名称，默认为None表示直接放在基础目录下

        Returns:
            str: 上传后的文件路径

        Raises:
            FileNotFoundError: 当源文件不存在时
            Exception: 上传过程中出现的其他异常
        """
        # 检查源文件是否存在
        if not os.path.exists(source_file_path):
            raise FileNotFoundError(f"源文件不存在: {source_file_path}")

        # 构建目标目录路径
        if target_folder:
            target_dir = os.path.join(self.upload_base_dir, target_folder)
            # 确保目标目录存在
            os.makedirs(target_dir, exist_ok=True)
        else:
            target_dir = self.upload_base_dir

        # 获取文件名
        filename = os.path.basename(source_file_path)
        # 构建目标文件路径
        target_file_path = os.path.join(target_dir, filename)

        # 复制文件到目标位置
        try:
            shutil.copy2(source_file_path, target_file_path)
            return target_file_path
        except Exception as e:
            raise Exception(f"文件上传失败: {str(e)}")

    def upload_files(
        self, source_file_paths: List[str], target_folder: Optional[str] = None
    ) -> List[str]:
        """
        批量上传文件到指定文件夹

        Args:
            source_file_paths (List[str]): 源文件路径列表
            target_folder (str, optional): 目标文件夹名称，默认为None表示直接放在基础目录下

        Returns:
            List[str]: 上传后的文件路径列表
        """
        uploaded_files = []

        for source_file_path in source_file_paths:
            uploaded_file_path = self.upload_file(source_file_path, target_folder)
            uploaded_files.append(uploaded_file_path)

        return uploaded_files

    def list_uploaded_files(self, folder: Optional[str] = None) -> List[str]:
        """
        列出已上传的文件

        Args:
            folder (str, optional): 特定文件夹名称，默认为None表示列出基础目录下的所有文件

        Returns:
            List[str]: 文件路径列表
        """
        target_dir = (
            os.path.join(self.upload_base_dir, folder)
            if folder
            else self.upload_base_dir
        )

        if not os.path.exists(target_dir):
            return []

        file_list = []
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            if os.path.isfile(item_path):
                file_list.append(item_path)

        return file_list


# 示例用法
if __name__ == "__main__":
    # 创建文件上传器实例
    uploader = FileUploader("uploads")

    # 上传单个文件
    # uploaded_file = uploader.upload_file("/path/to/source/file.txt", "documents")
    # print(f"上传完成: {uploaded_file}")

    # 批量上传文件
    # source_files = ["/path/to/file1.txt", "/path/to/file2.txt"]
    # uploaded_files = uploader.upload_files(source_files, "images")
    # print(f"批量上传完成: {uploaded_files}")

    # 列出已上传的文件
    # files = uploader.list_uploaded_files("images")
    # print(f"已上传文件: {files}")
