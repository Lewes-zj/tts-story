"""用户有声故事书数据访问对象"""

import pymysql
from typing import List, Dict, Any, Optional
from scripts.base_dao import BaseDAO
import logging

logger = logging.getLogger(__name__)


class UserStoryBookDAO(BaseDAO):
    """用户有声故事书数据访问对象"""

    def insert(self, user_id: int, role_id: int, story_id: int, story_book_path: str) -> int:
        """插入用户有声故事书记录"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """INSERT INTO user_story_books (user_id, role_id, story_id, story_book_path)
                         VALUES (%s, %s, %s, %s)"""
                cursor.execute(sql, (user_id, role_id, story_id, story_book_path))
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

    def find_by_user_role_story(self, user_id: int, role_id: int, story_id: int) -> Optional[Dict[str, Any]]:
        """根据用户ID、角色ID和故事ID查找记录"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """SELECT * FROM user_story_books 
                         WHERE user_id = %s AND role_id = %s AND story_id = %s
                         ORDER BY id DESC LIMIT 1"""
                cursor.execute(sql, (user_id, role_id, story_id))
                return cursor.fetchone()
        finally:
            conn.close()

    def find_list_by_user_id(self, user_id: int, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        """根据用户ID查找故事书列表"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                offset = (page - 1) * size
                sql = """SELECT * FROM user_story_books 
                         WHERE user_id = %s
                         ORDER BY create_time DESC LIMIT %s, %s"""
                cursor.execute(sql, (user_id, offset, size))
                return cursor.fetchall()
        finally:
            conn.close()

    def count_by_user_id(self, user_id: int) -> int:
        """统计用户故事书数量"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT COUNT(*) as total FROM user_story_books WHERE user_id = %s"
                cursor.execute(sql, (user_id,))
                result = cursor.fetchone()
                return result[0] if result else 0
        finally:
            conn.close()

