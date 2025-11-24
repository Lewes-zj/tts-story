"""角色数据访问对象"""

import pymysql
from typing import List, Dict, Any, Optional
from scripts.base_dao import BaseDAO
import logging

logger = logging.getLogger(__name__)


class CharacterDAO(BaseDAO):
    """角色数据访问对象"""

    def insert(self, role_name: str, user_id: int) -> int:
        """插入新角色"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """INSERT INTO role (role_name, create_time, create_user, update_time, update_user, is_delete)
                         VALUES (%s, NOW(), %s, NOW(), %s, 0)"""
                cursor.execute(sql, (role_name, user_id, user_id))
                conn.commit()
                role_id = cursor.lastrowid
                
                # 关联用户和角色
                sql2 = """INSERT INTO user_role (user_id, role_id, create_time, create_user, update_time, update_user, is_delete)
                          VALUES (%s, %s, NOW(), %s, NOW(), %s, 0)"""
                cursor.execute(sql2, (user_id, role_id, user_id, user_id))
                conn.commit()
                return role_id
        finally:
            conn.close()

    def find_by_user_id(self, user_id: int) -> List[Dict[str, Any]]:
        """根据用户ID查找角色列表"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """SELECT r.* FROM role r
                         INNER JOIN user_role ur ON r.id = ur.role_id
                         WHERE ur.user_id = %s AND r.is_delete = 0 AND ur.is_delete = 0
                         ORDER BY r.create_time DESC"""
                cursor.execute(sql, (user_id,))
                return cursor.fetchall()
        finally:
            conn.close()

    def find_by_id(self, role_id: int) -> Optional[Dict[str, Any]]:
        """根据ID查找角色"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM role WHERE id = %s AND is_delete = 0"
                cursor.execute(sql, (role_id,))
                return cursor.fetchone()
        finally:
            conn.close()

