"""用户数据访问对象"""

import pymysql
from typing import Optional, Dict, Any
from scripts.base_dao import BaseDAO
import logging

logger = logging.getLogger(__name__)


class UserDAO(BaseDAO):
    """用户数据访问对象"""

    def find_by_account(self, account: str) -> Optional[Dict[str, Any]]:
        """根据账户名查找用户"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM `user` WHERE account = %s AND is_delete = 0"
                cursor.execute(sql, (account,))
                return cursor.fetchone()
        finally:
            conn.close()

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """根据邮箱查找用户"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM `user` WHERE email = %s AND is_delete = 0"
                cursor.execute(sql, (email,))
                return cursor.fetchone()
        finally:
            conn.close()

    def find_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据ID查找用户"""
        conn = self._get_db_connection()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM `user` WHERE id = %s AND is_delete = 0"
                cursor.execute(sql, (user_id,))
                return cursor.fetchone()
        finally:
            conn.close()

    def insert(self, account: str, email: str, password: str, name: str) -> int:
        """
        插入新用户
        
        Args:
            account: 账户名
            email: 邮箱
            password: 已加密的密码（bcrypt hash）
            name: 用户名
        """
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """INSERT INTO `user` (account, email, password, name, gender, register_time, update_time, is_delete)
                         VALUES (%s, %s, %s, %s, -1, NOW(), NOW(), 0)"""
                cursor.execute(sql, (account, email, password, name))
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

