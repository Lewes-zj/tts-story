"""任务数据访问对象"""

import pymysql
from typing import List, Dict, Any, Optional
from scripts.base_dao import BaseDAO
import logging

logger = logging.getLogger(__name__)


class TaskDAO(BaseDAO):
    """任务数据访问对象"""

    def insert(self, user_id: int, story_id: int, character_id: int, status: str = "generating") -> int:
        """插入新任务"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """INSERT INTO task (user_id, story_id, character_id, status, create_time, update_time, is_delete)
                         VALUES (%s, %s, %s, %s, NOW(), NOW(), 0)"""
                cursor.execute(sql, (user_id, story_id, character_id, status))
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

    def find_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        """根据ID查找任务"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM task WHERE id = %s AND is_delete = 0"
                cursor.execute(sql, (task_id,))
                return cursor.fetchone()
        finally:
            conn.close()

    def find_by_user_id(self, user_id: int, status: Optional[str] = None, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        """根据用户ID查找任务列表"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM task WHERE user_id = %s AND is_delete = 0"
                params = [user_id]
                if status:
                    sql += " AND status = %s"
                    params.append(status)
                sql += " ORDER BY create_time DESC LIMIT %s, %s"
                params.extend([(page - 1) * size, size])
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            conn.close()

    def count_by_user_id(self, user_id: int, status: Optional[str] = None) -> int:
        """统计用户任务数量"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT COUNT(*) as total FROM task WHERE user_id = %s AND is_delete = 0"
                params = [user_id]
                if status:
                    sql += " AND status = %s"
                    params.append(status)
                cursor.execute(sql, params)
                result = cursor.fetchone()
                return result[0] if result else 0
        finally:
            conn.close()

    def update(self, task_id: int, status: Optional[str] = None, audio_url: Optional[str] = None, error_message: Optional[str] = None):
        """更新任务"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                updates = []
                params = []
                if status:
                    updates.append("status = %s")
                    params.append(status)
                if audio_url:
                    updates.append("audio_url = %s")
                    params.append(audio_url)
                if error_message:
                    updates.append("error_message = %s")
                    params.append(error_message)
                if updates:
                    updates.append("update_time = NOW()")
                    params.append(task_id)
                    sql = f"UPDATE task SET {', '.join(updates)} WHERE id = %s"
                    cursor.execute(sql, params)
                    conn.commit()
        finally:
            conn.close()

