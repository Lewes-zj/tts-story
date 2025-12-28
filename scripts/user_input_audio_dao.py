"""用户输入音频数据访问对象"""

import pymysql
from typing import Optional, Dict, Any
from scripts.base_dao import BaseDAO
import logging

logger = logging.getLogger(__name__)


class UserInputAudioDAO(BaseDAO):
    """用户输入音频数据访问对象"""

    def insert(self, user_id: int, role_id: int, init_input: str, clean_input: Optional[str] = None, cosy_voice: Optional[str] = None, tts_voice: Optional[str] = None) -> int:
        """插入用户输入音频记录"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """INSERT INTO user_input_audio (user_id, role_id, init_input, clean_input, cosy_voice, tts_voice)
                         VALUES (%s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (user_id, role_id, init_input, clean_input, cosy_voice, tts_voice))
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

    def find_by_user_and_role(self, user_id: int, role_id: int) -> Optional[Dict[str, Any]]:
        """根据用户ID和角色ID查找用户输入音频"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """SELECT * FROM user_input_audio 
                         WHERE user_id = %s AND role_id = %s
                         ORDER BY id DESC
                         LIMIT 1"""
                cursor.execute(sql, (user_id, role_id))
                return cursor.fetchone()
        finally:
            conn.close()

    def update_clean_input(self, user_id: int, role_id: int, clean_input: str) -> bool:
        """更新用户输入音频的 clean_input 字段"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """UPDATE user_input_audio 
                         SET clean_input = %s
                         WHERE user_id = %s AND role_id = %s
                         ORDER BY id DESC
                         LIMIT 1"""
                cursor.execute(sql, (clean_input, user_id, role_id))
                conn.commit()
                return cursor.rowcount > 0
        finally:
            conn.close()

    def update_cosy_voice(self, user_id: int, role_id: int, cosy_voice: str) -> bool:
        """更新用户输入音频的 cosy_voice 字段"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """UPDATE user_input_audio 
                         SET cosy_voice = %s
                         WHERE user_id = %s AND role_id = %s
                         ORDER BY id DESC
                         LIMIT 1"""
                cursor.execute(sql, (cosy_voice, user_id, role_id))
                conn.commit()
                return cursor.rowcount > 0
        finally:
            conn.close()

    def update_tts_voice(self, user_id: int, role_id: int, tts_voice: str) -> bool:
        """更新用户输入音频的 tts_voice 字段"""
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """UPDATE user_input_audio 
                         SET tts_voice = %s
                         WHERE user_id = %s AND role_id = %s
                         ORDER BY id DESC
                         LIMIT 1"""
                cursor.execute(sql, (tts_voice, user_id, role_id))
                conn.commit()
                return cursor.rowcount > 0
        finally:
            conn.close()

