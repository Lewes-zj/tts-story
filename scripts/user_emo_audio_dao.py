"""用户情绪音频数据访问对象
专门处理user_emo_audio表的数据库操作
"""

import pymysql
from typing import List, Optional, Dict, Any
from scripts.base_dao import BaseDAO
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class UserEmoAudioDAO(BaseDAO):
    """用户情绪音频数据访问对象"""

    def __init__(self, config_path=None):
        """
        初始化用户情绪音频DAO

        Args:
            config_path (str, optional): 数据库配置文件路径，默认使用BaseDAO的默认路径
        """
        logger.info("初始化UserEmoAudioDAO")
        if config_path:
            logger.info(f"使用指定配置路径: {config_path}")
            super().__init__(config_path)
        else:
            logger.info("使用默认配置路径")
            super().__init__()  # 使用BaseDAO的默认路径
        logger.info("UserEmoAudioDAO初始化完成")

    def insert(
        self,
        user_id: int,
        role_id: int,
        emo_type: str,
        spk_audio_prompt: str,
        spk_emo_vector: str,
        spk_emo_alpha: float,
        emo_audio_prompt: str,
        emo_vector: str,
        emo_alpha: float,
    ) -> int:
        """
        插入用户情绪音频记录

        Args:
            user_id (int): 用户ID
            role_id (int): 角色ID
            emo_type (str): 情绪类型
            spk_audio_prompt (str): 高质量input音频
            spk_emo_vector (str): 高质量input音频情绪向量
            spk_emo_alpha (float): 高质量input音频情绪混合系数
            emo_audio_prompt (str): 情绪引导音频
            emo_vector (str): 情绪引导音频情绪向量
            emo_alpha (float): 情绪引导音频情绪混合系数

        Returns:
            int: 插入记录的ID
        """
        logger.info(f"插入用户情绪音频记录: user_id={user_id}, role_id={role_id}, emo_type={emo_type}")
        logger.debug(f"spk_audio_prompt={spk_audio_prompt}, spk_emo_alpha={spk_emo_alpha}, emo_audio_prompt={emo_audio_prompt}, emo_alpha={emo_alpha}")
        
        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                INSERT INTO user_emo_audio 
                (user_id, role_id, emo_type, spk_audio_prompt, spk_emo_vector, spk_emo_alpha, 
                emo_audio_prompt, emo_vector, emo_alpha)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                logger.debug("执行SQL: INSERT用户情绪音频记录")
                cursor.execute(
                    sql,
                    (
                        user_id,
                        role_id,
                        emo_type,
                        spk_audio_prompt,
                        spk_emo_vector,
                        spk_emo_alpha,
                        emo_audio_prompt,
                        emo_vector,
                        emo_alpha,
                    ),
                )
                connection.commit()
                record_id = cursor.lastrowid
                logger.info(f"用户情绪音频记录插入成功，记录ID: {record_id}")
                return record_id
        except Exception as e:
            logger.error(f"插入用户情绪音频记录时发生错误: {str(e)}")
            raise
        finally:
            connection.close()
            logger.debug("数据库连接已关闭")

    def update(self, record_id: int, **kwargs) -> bool:
        """
        更新用户情绪音频记录

        Args:
            record_id (int): 记录ID
            **kwargs: 要更新的字段和值

        Returns:
            bool: 更新是否成功
        """
        logger.info(f"更新用户情绪音频记录: record_id={record_id}")
        logger.debug(f"更新字段: {kwargs}")
        
        if not kwargs:
            logger.warning("没有提供要更新的字段")
            return False

        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                # 构建更新SQL
                set_clause = ", ".join([f"{key} = %s" for key in kwargs.keys()])
                sql = f"UPDATE user_emo_audio SET {set_clause} WHERE id = %s"
                logger.debug(f"执行SQL: {sql}")

                # 执行更新
                values = list(kwargs.values()) + [record_id]
                cursor.execute(sql, values)
                connection.commit()
                success = cursor.rowcount > 0
                logger.info(f"用户情绪音频记录更新{'成功' if success else '失败'}")
                return success
        except Exception as e:
            logger.error(f"更新用户情绪音频记录时发生错误: {str(e)}")
            raise
        finally:
            connection.close()
            logger.debug("数据库连接已关闭")

    def delete(self, record_id: int) -> bool:
        """
        删除用户情绪音频记录

        Args:
            record_id (int): 记录ID

        Returns:
            bool: 删除是否成功
        """
        logger.info(f"删除用户情绪音频记录: record_id={record_id}")
        
        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                sql = "DELETE FROM user_emo_audio WHERE id = %s"
                logger.debug(f"执行SQL: {sql}")
                cursor.execute(sql, (record_id,))
                connection.commit()
                success = cursor.rowcount > 0
                logger.info(f"用户情绪音频记录删除{'成功' if success else '失败'}")
                return success
        except Exception as e:
            logger.error(f"删除用户情绪音频记录时发生错误: {str(e)}")
            raise
        finally:
            connection.close()
            logger.debug("数据库连接已关闭")

    def query_by_user_role(
        self, user_id: int, role_id: int, emo_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        根据用户ID和角色ID查询用户情绪音频记录，可选情绪类型过滤

        Args:
            user_id (int): 用户ID（必填）
            role_id (int): 角色ID（必填）
            emo_type (str, optional): 情绪类型（非必填）

        Returns:
            List[Dict[str, Any]]: 查询结果列表
        """
        logger.info(f"查询用户情绪音频记录: user_id={user_id}, role_id={role_id}, emo_type={emo_type}")
        
        connection = self._get_db_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                if emo_type:
                    sql = "SELECT * FROM user_emo_audio WHERE user_id = %s AND role_id = %s AND emo_type = %s"
                    logger.debug(f"执行SQL: {sql}")
                    cursor.execute(sql, (user_id, role_id, emo_type))
                else:
                    sql = "SELECT * FROM user_emo_audio WHERE user_id = %s AND role_id = %s"
                    logger.debug(f"执行SQL: {sql}")
                    cursor.execute(sql, (user_id, role_id))

                results = cursor.fetchall()
                logger.info(f"查询完成，返回{len(results)}条记录")
                # 确保返回的是列表类型
                return list(results) if results else []
        except Exception as e:
            logger.error(f"查询用户情绪音频记录时发生错误: {str(e)}")
            raise
        finally:
            connection.close()
            logger.debug("数据库连接已关闭")

    def query_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """
        根据记录ID查询用户情绪音频记录

        Args:
            record_id (int): 记录ID

        Returns:
            Optional[Dict[str, Any]]: 查询结果，如果未找到返回None
        """
        logger.info(f"根据ID查询用户情绪音频记录: record_id={record_id}")
        
        connection = self._get_db_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM user_emo_audio WHERE id = %s"
                logger.debug(f"执行SQL: {sql}")
                cursor.execute(sql, (record_id,))
                result = cursor.fetchone()
                logger.info(f"ID查询{'成功' if result else '未找到记录'}")
                return result
        except Exception as e:
            logger.error(f"根据ID查询用户情绪音频记录时发生错误: {str(e)}")
            raise
        finally:
            connection.close()
            logger.debug("数据库连接已关闭")

    def query_by_user_role_as_map(self, user_id: int, role_id: int) -> Dict[str, Dict[str, Any]]:
        """
        根据用户ID和角色ID查询用户情绪音频记录，并将结果转换为映射
        键（key）是 emo_type（情绪类型），值（value）是完整的数据记录

        Args:
            user_id (int): 用户ID
            role_id (int): 角色ID

        Returns:
            Dict[str, Dict[str, Any]]: 以emo_type为键的记录映射
        """
        logger.info(f"根据用户ID和角色ID查询用户情绪音频记录并转换为映射: user_id={user_id}, role_id={role_id}")
        
        connection = self._get_db_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM user_emo_audio WHERE user_id = %s AND role_id = %s"
                logger.debug(f"执行SQL: {sql}")
                cursor.execute(sql, (user_id, role_id))
                results = cursor.fetchall()
                
                # 转换为以emo_type为键的映射
                records_map = {}
                if results:
                    for row in results:
                        emo_type = row['emo_type']
                        # 如果同一个emo_type有多个记录，保留第一个并记录警告
                        if emo_type in records_map:
                            logger.warning(f"发现重复的emo_type '{emo_type}'，将保留第一条记录")
                        else:
                            records_map[emo_type] = row
                
                logger.info(f"查询完成，返回{len(records_map)}条记录")
                return records_map
        except Exception as e:
            logger.error(f"根据用户ID和角色ID查询用户情绪音频记录并转换为映射时发生错误: {str(e)}")
            raise
        finally:
            connection.close()
            logger.debug("数据库连接已关闭")

# 示例用法
if __name__ == "__main__":
    # 创建DAO实例
    dao = UserEmoAudioDAO()

    # 插入记录
    # record_id = dao.insert(
    #     user_id=1,
    #     role_id=1,
    #     emo_type="happy",
    #     spk_audio_prompt="/path/to/spk_audio.wav",
    #     spk_emo_vector="[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]",
    #     spk_emo_alpha=0.75,
    #     emo_audio_prompt="/path/to/emo_audio.wav",
    #     emo_vector="[0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]",
    #     emo_alpha=0.85
    # )
    # print(f"插入记录ID: {record_id}")

    # 查询记录
    # records = dao.query_by_user_role(user_id=1, role_id=1, emo_type="happy")
    # print(f"查询结果: {records}")

    # 根据ID查询记录
    # record = dao.query_by_id(record_id=1)
    # print(f"ID查询结果: {record}")

    # 更新记录
    # success = dao.update(record_id=1, emo_type="excited")
    # print(f"更新结果: {success}")

    # 删除记录
    # success = dao.delete(record_id=1)
    # print(f"删除结果: {success}")
    