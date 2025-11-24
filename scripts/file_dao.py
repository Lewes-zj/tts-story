"""文件数据访问对象"""

import pymysql
from typing import Optional, Dict, Any
from scripts.base_dao import BaseDAO
import logging

logger = logging.getLogger(__name__)


class FileDAO(BaseDAO):
    """文件数据访问对象"""

    def insert(self, user_id: int, file_name: str, file_url: str, file_type: Optional[str] = None, file_size: Optional[int] = None) -> int:
        """插入文件记录"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """INSERT INTO file (user_id, file_name, file_url, file_type, file_size, create_time, update_time, is_delete)
                         VALUES (%s, %s, %s, %s, %s, NOW(), NOW(), 0)"""
                cursor.execute(sql, (user_id, file_name, file_url, file_type, file_size))
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

    def find_by_id(self, file_id: int) -> Optional[Dict[str, Any]]:
        """根据ID查找文件"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM file WHERE id = %s AND is_delete = 0"
                cursor.execute(sql, (file_id,))
                return cursor.fetchone()
        finally:
            conn.close()

