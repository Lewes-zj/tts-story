"""基础数据访问对象
提供数据库配置加载和连接管理的基类
"""

import yaml
import pymysql
import os
from typing import Dict, Any


class BaseDAO:
    """基础数据访问对象"""

    # 类变量，用于缓存数据库配置
    _db_config = None
    _config_path = None

    def __init__(self, config_path="config/database.yaml"):
        """
        初始化基础DAO

        Args:
            config_path (str): 数据库配置文件路径
        """
        # 使用项目根目录定位方法获取配置文件的绝对路径
        if not os.path.isabs(config_path):
            # 获取项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # 构建配置文件的绝对路径
            config_path = os.path.join(project_root, config_path)

        # 如果配置路径不同，或者配置尚未加载，则加载配置
        if BaseDAO._config_path != config_path or BaseDAO._db_config is None:
            BaseDAO._config_path = config_path
            BaseDAO._db_config = self._load_db_config()

        self.db_config = BaseDAO._db_config

    def _load_db_config(self) -> Dict[str, Any]:
        """
        加载数据库配置

        Returns:
            dict: 数据库配置信息
        """
        # 确保_config_path不为None
        if BaseDAO._config_path is None:
            # 获取项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # 构建配置文件的绝对路径
            config_path = os.path.join(project_root, "config/database.yaml")
        else:
            config_path = BaseDAO._config_path

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config["mysql"]

    def _get_db_connection(self):
        """
        获取数据库连接

        Returns:
            pymysql.Connection: 数据库连接对象
        """
        return pymysql.connect(
            host=self.db_config["host"],
            port=self.db_config["port"],
            user=self.db_config["user"],
            password=self.db_config["password"],
            database=self.db_config["database"],
            charset=self.db_config["charset"],
        )


# 示例用法
if __name__ == "__main__":
    # 创建基础DAO实例
    base_dao = BaseDAO()
    print(f"数据库配置: {base_dao.db_config}")
