"""基础数据访问对象
提供数据库配置加载和连接管理的基类
"""

import yaml
import pymysql
import os
import logging
from typing import Dict, Any

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
        logger.info(f"初始化BaseDAO，配置路径: {config_path}")
        
        # 使用项目根目录定位方法获取配置文件的绝对路径
        if not os.path.isabs(config_path):
            # 获取项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # 构建配置文件的绝对路径
            config_path = os.path.join(project_root, config_path)
            logger.debug(f"转换为绝对路径: {config_path}")

        # 如果配置路径不同，或者配置尚未加载，则加载配置
        if BaseDAO._config_path != config_path or BaseDAO._db_config is None:
            logger.info("加载新的数据库配置")
            BaseDAO._config_path = config_path
            BaseDAO._db_config = self._load_db_config()
        else:
            logger.info("使用缓存的数据库配置")

        self.db_config = BaseDAO._db_config
        logger.info("BaseDAO初始化完成")

    def _load_db_config(self) -> Dict[str, Any]:
        """
        加载数据库配置

        Returns:
            dict: 数据库配置信息
        """
        logger.info("开始加载数据库配置")
        
        # 确保_config_path不为None
        if BaseDAO._config_path is None:
            # 获取项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # 构建配置文件的绝对路径
            config_path = os.path.join(project_root, "config/database.yaml")
            logger.debug(f"使用默认配置路径: {config_path}")
        else:
            config_path = BaseDAO._config_path
            logger.debug(f"使用指定配置路径: {config_path}")

        logger.info(f"读取配置文件: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logger.info("数据库配置加载完成")
        return config["mysql"]

    def _get_db_connection(self):
        """
        获取数据库连接

        Returns:
            pymysql.Connection: 数据库连接对象
        """
        logger.info("创建数据库连接")
        logger.debug(f"连接参数: host={self.db_config['host']}, port={self.db_config['port']}, user={self.db_config['user']}, database={self.db_config['database']}")
        
        connection = pymysql.connect(
            host=self.db_config["host"],
            port=self.db_config["port"],
            user=self.db_config["user"],
            password=self.db_config["password"],
            database=self.db_config["database"],
            charset=self.db_config["charset"],
        )
        logger.info("数据库连接创建成功")
        return connection


# 示例用法
if __name__ == "__main__":
    # 创建基础DAO实例
    base_dao = BaseDAO()
    print(f"数据库配置: {base_dao.db_config}")
    