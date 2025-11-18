"""情绪向量配置数据访问对象
专门处理emo_vector_config表的数据库操作
"""

import pymysql
from typing import List, Optional, Dict, Any
from scripts.base_dao import BaseDAO
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EmoVectorConfigDAO(BaseDAO):
    """情绪向量配置数据访问对象"""

    def __init__(self, config_path=None):
        """
        初始化情绪向量配置DAO

        Args:
            config_path (str, optional): 数据库配置文件路径，默认使用BaseDAO的默认路径
        """
        logger.info("初始化EmoVectorConfigDAO")
        if config_path:
            logger.info(f"使用指定配置路径: {config_path}")
            super().__init__(config_path)
        else:
            logger.info("使用默认配置路径")
            super().__init__()  # 使用BaseDAO的默认路径
        logger.info("EmoVectorConfigDAO初始化完成")

    def fetch_all_configs(self) -> List[Dict[str, Any]]:
        """
        从数据库查询emo_vector_config表的所有数据

        Returns:
            List[Dict[str, Any]]: 配置数据列表
        """
        logger.info("查询所有情绪向量配置")
        
        connection = self._get_db_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # 查询所有情绪向量配置
                sql = "SELECT * FROM emo_vector_config"
                logger.debug(f"执行SQL: {sql}")
                cursor.execute(sql)
                results = cursor.fetchall()
                logger.info(f"查询完成，返回{len(results)}条配置")
                return list(results) if results else []
        except Exception as e:
            logger.error(f"查询所有情绪向量配置时发生错误: {str(e)}")
            raise
        finally:
            connection.close()
            logger.debug("数据库连接已关闭")

    def fetch_config_by_id(self, config_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID查询emo_vector_config表的特定数据

        Args:
            config_id (int): 配置ID

        Returns:
            Optional[Dict[str, Any]]: 配置数据字典，如果未找到返回None
        """
        logger.info(f"根据ID查询情绪向量配置: config_id={config_id}")
        
        connection = self._get_db_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # 根据ID查询情绪向量配置
                sql = "SELECT * FROM emo_vector_config WHERE id = %s"
                logger.debug(f"执行SQL: {sql}")
                cursor.execute(sql, (config_id,))
                result = cursor.fetchone()
                logger.info(f"ID查询{'成功' if result else '未找到配置'}")
                return result
        except Exception as e:
            logger.error(f"根据ID查询情绪向量配置时发生错误: {str(e)}")
            raise
        finally:
            connection.close()
            logger.debug("数据库连接已关闭")

    def fetch_configs_by_type(self, emo_type: str) -> List[Dict[str, Any]]:
        """
        根据情绪类型查询emo_vector_config表的数据

        Args:
            emo_type (str): 情绪类型

        Returns:
            List[Dict[str, Any]]: 配置数据列表
        """
        logger.info(f"根据情绪类型查询情绪向量配置: emo_type={emo_type}")
        
        connection = self._get_db_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # 根据情绪类型查询情绪向量配置
                sql = "SELECT * FROM emo_vector_config WHERE type = %s"
                logger.debug(f"执行SQL: {sql}")
                cursor.execute(sql, (emo_type,))
                results = cursor.fetchall()
                logger.info(f"情绪类型查询完成，返回{len(results)}条配置")
                return list(results) if results else []
        except Exception as e:
            logger.error(f"根据情绪类型查询情绪向量配置时发生错误: {str(e)}")
            raise
        finally:
            connection.close()
            logger.debug("数据库连接已关闭")


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