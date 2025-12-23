"""用户有声故事书数据访问对象"""

import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import pymysql

from scripts.base_dao import BaseDAO

logger = logging.getLogger(__name__)


class UserStoryBookDAO(BaseDAO):
    """用户有声故事书数据访问对象"""

    def __init__(self) -> None:
        super().__init__()
        # 允许通过环境变量配置可对外访问的前缀，默认尝试复用 FILE_URL_PREFIX
        self._public_prefix = os.getenv("STORY_BOOK_URL_PREFIX") or os.getenv("FILE_URL_PREFIX", "")

    def _build_public_path(self, story_book_path: str) -> str:
        """将存储路径标准化为可外网访问的完整路径/URL。"""
        if not story_book_path:
            return story_book_path

        # 已是完整 URL，直接返回
        if story_book_path.startswith(("http://", "https://")):
            return story_book_path

        # 如果配置了对外前缀，拼接生成可访问的URL
        if self._public_prefix:
            prefix = self._public_prefix if self._public_prefix.endswith("/") else f"{self._public_prefix}/"
            return urljoin(prefix, story_book_path.lstrip("/"))

        # 兜底返回原值，避免因配置缺失导致插入失败
        return story_book_path

    def insert(self, user_id: int, role_id: int, story_id: int, story_book_path: str) -> int:
        """插入用户有声故事书记录，存储可对外访问的完整路径"""
        public_path = self._build_public_path(story_book_path)

        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """INSERT INTO user_story_books (user_id, role_id, story_id, story_book_path)
                         VALUES (%s, %s, %s, %s)"""
                cursor.execute(sql, (user_id, role_id, story_id, public_path))
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

    def normalize_path(self, story_book_path: str) -> str:
        """对外暴露的路径规范化辅助方法，便于其他调用方复用。"""
        return self._build_public_path(story_book_path)

    def find_by_user_role_story(self, user_id: int, role_id: int, story_id: int) -> Optional[Dict[str, Any]]:
        """根据用户ID、角色ID和故事ID查找记录"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """SELECT * FROM user_story_books 
                         WHERE user_id = %s AND role_id = %s AND story_id = %s
                         ORDER BY id DESC LIMIT 1"""
                cursor.execute(sql, (user_id, role_id, story_id))
                record = cursor.fetchone()
                if record and record.get("story_book_path"):
                    # 兼容历史数据：读取时也补全为可访问URL
                    record["story_book_path"] = self._build_public_path(record["story_book_path"])
                return record
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
                records = cursor.fetchall()
                for record in records:
                    if record.get("story_book_path"):
                        record["story_book_path"] = self._build_public_path(record["story_book_path"])
                return records
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
