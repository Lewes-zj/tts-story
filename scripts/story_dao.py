"""故事数据访问对象"""

import os
import yaml
import pymysql
from typing import List, Dict, Any, Optional
from scripts.base_dao import BaseDAO
import logging

logger = logging.getLogger(__name__)

# 故事路径映射配置缓存
_story_path_mapping_cache = None
_story_path_config_mtime = None

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

    def _load_story_path_mapping(self) -> Dict[int, str]:
        """
        从配置文件加载故事路径映射
        支持热更新：如果配置文件被修改，会自动重新加载

        Returns:
            故事ID到文件路径的映射字典
        """
        global _story_path_mapping_cache, _story_path_config_mtime

        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config", "story_path_mapping.yaml")

        # 检查配置文件是否存在
        if not os.path.exists(config_path):
            logger.error(f"故事路径映射配置文件不存在: {config_path}")
            return {}

        # 获取文件修改时间
        current_mtime = os.path.getmtime(config_path)

        # 如果配置文件未修改且缓存存在，直接返回缓存
        if (_story_path_mapping_cache is not None and
            _story_path_config_mtime is not None and
            current_mtime == _story_path_config_mtime):
            return _story_path_mapping_cache

        # 重新加载配置文件
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # 提取映射关系
            mapping = config.get("story_path_mapping", {})

            # 转换为整数键的字典
            story_path_mapping = {}
            for key, value in mapping.items():
                try:
                    story_id = int(key)
                    story_path_mapping[story_id] = value
                except (ValueError, TypeError):
                    logger.warning(f"无效的故事ID配置: {key} = {value}")

            # 更新缓存
            _story_path_mapping_cache = story_path_mapping
            _story_path_config_mtime = current_mtime
            
            logger.info(f"成功加载故事路径映射配置，共 {len(story_path_mapping)} 个映射")
            return story_path_mapping

        except Exception as e:
            logger.error(f"加载故事路径映射配置失败: {str(e)}")
            # 如果加载失败，返回空字典或使用默认缓存
            return _story_path_mapping_cache if _story_path_mapping_cache else {}

    def get_story_path(self, story_id: int) -> Optional[str]:
        """
        获取故事的JSON文件路径
        从配置文件读取映射关系，支持热更新

        Args:
            story_id: 故事ID

        Returns:
            故事JSON文件的路径，如果未配置则返回None
        """
        # 从配置文件加载映射关系（支持热更新）
        story_path_mapping = self._load_story_path_mapping()

        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 从映射中获取相对路径
        relative_path = story_path_mapping.get(story_id)
        if not relative_path:
            logger.warning(f"未找到故事ID {story_id} 对应的JSON文件路径，请检查 config/story_path_mapping.yaml 配置")
            return None

        # 构建绝对路径
        story_path = os.path.join(project_root, relative_path)

        # 验证文件是否存在
        if not os.path.exists(story_path):
            logger.warning(f"故事JSON文件不存在: {story_path}")
            return None

        return story_path

