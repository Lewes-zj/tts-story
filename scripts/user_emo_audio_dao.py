"""用户情绪音频数据访问对象
专门处理user_emo_audio表的数据库操作
"""

import pymysql
from typing import List, Optional, Dict, Any
from scripts.base_dao import BaseDAO


class UserEmoAudioDAO(BaseDAO):
    """用户情绪音频数据访问对象"""

    def __init__(self, config_path=None):
        """
        初始化用户情绪音频DAO

        Args:
            config_path (str, optional): 数据库配置文件路径，默认使用BaseDAO的默认路径
        """
        if config_path:
            super().__init__(config_path)
        else:
            super().__init__()  # 使用BaseDAO的默认路径

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
        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                INSERT INTO user_emo_audio 
                (user_id, role_id, emo_type, spk_audio_prompt, spk_emo_vector, spk_emo_alpha, 
                emo_audio_prompt, emo_vector, emo_alpha)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
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
                return cursor.lastrowid
        finally:
            connection.close()

    def update(self, record_id: int, **kwargs) -> bool:
        """
        更新用户情绪音频记录

        Args:
            record_id (int): 记录ID
            **kwargs: 要更新的字段和值

        Returns:
            bool: 更新是否成功
        """
        if not kwargs:
            return False

        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                # 构建更新SQL
                set_clause = ", ".join([f"{key} = %s" for key in kwargs.keys()])
                sql = f"UPDATE user_emo_audio SET {set_clause} WHERE id = %s"

                # 执行更新
                values = list(kwargs.values()) + [record_id]
                cursor.execute(sql, values)
                connection.commit()
                return cursor.rowcount > 0
        finally:
            connection.close()

    def delete(self, record_id: int) -> bool:
        """
        删除用户情绪音频记录

        Args:
            record_id (int): 记录ID

        Returns:
            bool: 删除是否成功
        """
        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                sql = "DELETE FROM user_emo_audio WHERE id = %s"
                cursor.execute(sql, (record_id,))
                connection.commit()
                return cursor.rowcount > 0
        finally:
            connection.close()

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
        connection = self._get_db_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                if emo_type:
                    sql = "SELECT * FROM user_emo_audio WHERE user_id = %s AND role_id = %s AND emo_type = %s"
                    cursor.execute(sql, (user_id, role_id, emo_type))
                else:
                    sql = "SELECT * FROM user_emo_audio WHERE user_id = %s AND role_id = %s"
                    cursor.execute(sql, (user_id, role_id))

                results = cursor.fetchall()
                # 确保返回的是列表类型
                return list(results) if results else []
        finally:
            connection.close()

    def query_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """
        根据记录ID查询用户情绪音频记录

        Args:
            record_id (int): 记录ID

        Returns:
            Optional[Dict[str, Any]]: 查询结果，如果未找到返回None
        """
        connection = self._get_db_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM user_emo_audio WHERE id = %s"
                cursor.execute(sql, (record_id,))
                result = cursor.fetchone()
                return result
        finally:
            connection.close()


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
