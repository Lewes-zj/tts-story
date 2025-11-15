"""
情绪向量配置数据访问对象
专门处理emo_vector_config表的数据库操作
"""

import pymysql
from typing import List, Optional, Dict, Any
from scripts.base_dao import BaseDAO


class EmoVectorConfigDAO(BaseDAO):
    """情绪向量配置数据访问对象"""

    def __init__(self, config_path="config/database.yaml"):
        """
        初始化情绪向量配置DAO

        Args:
            config_path (str): 数据库配置文件路径
        """
        super().__init__(config_path)

    def fetch_all_configs(self) -> List[Dict[str, Any]]:
        """
        从数据库查询emo_vector_config表的所有数据

        Returns:
            List[Dict[str, Any]]: 配置数据列表
        """
        connection = self._get_db_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # 查询所有情绪向量配置
                sql = "SELECT * FROM emo_vector_config"
                cursor.execute(sql)
                results = cursor.fetchall()
                return list(results) if results else []
        finally:
            connection.close()

    def fetch_config_by_id(self, config_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID查询emo_vector_config表的特定数据

        Args:
            config_id (int): 配置ID

        Returns:
            Optional[Dict[str, Any]]: 配置数据字典，如果未找到返回None
        """
        connection = self._get_db_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # 根据ID查询情绪向量配置
                sql = "SELECT * FROM emo_vector_config WHERE id = %s"
                cursor.execute(sql, (config_id,))
                result = cursor.fetchone()
                return result
        finally:
            connection.close()

    def fetch_configs_by_type(self, emo_type: str) -> List[Dict[str, Any]]:
        """
        根据情绪类型查询emo_vector_config表的数据

        Args:
            emo_type (str): 情绪类型

        Returns:
            List[Dict[str, Any]]: 配置数据列表
        """
        connection = self._get_db_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # 根据情绪类型查询情绪向量配置
                sql = "SELECT * FROM emo_vector_config WHERE type = %s"
                cursor.execute(sql, (emo_type,))
                results = cursor.fetchall()
                return list(results) if results else []
        finally:
            connection.close()


# 示例用法
if __name__ == "__main__":
    # 创建DAO实例
    dao = EmoVectorConfigDAO()

    # 查询所有配置
    # all_configs = dao.fetch_all_configs()
    # print(f"所有配置: {all_configs}")

    # 根据ID查询配置
    # config = dao.fetch_config_by_id(1)
    # print(f"ID为1的配置: {config}")

    # 根据情绪类型查询配置
    # configs = dao.fetch_configs_by_type("happy")
    # print(f"happy类型的配置: {configs}")
