"""故事数据访问对象"""

import pymysql
from typing import List, Dict, Any, Optional
from scripts.base_dao import BaseDAO
import logging

logger = logging.getLogger(__name__)


class StoryDAO(BaseDAO):
    """故事数据访问对象"""

    def find_list(self, category: Optional[str] = None, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        """查找故事列表"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM story WHERE is_delete = 0"
                params = []
                if category:
                    sql += " AND category = %s"
                    params.append(category)
                sql += " ORDER BY create_time DESC LIMIT %s, %s"
                params.extend([(page - 1) * size, size])
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            conn.close()

    def count(self, category: Optional[str] = None) -> int:
        """统计故事数量"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT COUNT(*) as total FROM story WHERE is_delete = 0"
                params = []
                if category:
                    sql += " AND category = %s"
                    params.append(category)
                cursor.execute(sql, params)
                result = cursor.fetchone()
                return result[0] if result else 0
        finally:
            conn.close()

    def find_by_id(self, story_id: int) -> Optional[Dict[str, Any]]:
        """根据ID查找故事"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM story WHERE id = %s AND is_delete = 0"
                cursor.execute(sql, (story_id,))
                return cursor.fetchone()
        finally:
            conn.close()

    def get_story_content(self, story_id: int) -> str:
        """获取故事内容（从sub_story表）"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """SELECT GROUP_CONCAT(sub_story_content ORDER BY sort SEPARATOR '\n') as content
                         FROM sub_story
                         WHERE story_id = %s AND is_delete = 0"""
                cursor.execute(sql, (story_id,))
                result = cursor.fetchone()
                return result[0] if result and result[0] else ""
        finally:
            conn.close()

