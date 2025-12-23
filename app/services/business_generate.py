"""
业务层音频生成服务

提供基于ID的音频生成功能，自动处理配置文件读取和数据库查询
"""

import json
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class BusinessGenerateService:
    """业务层音频生成服务"""

    def __init__(self):
        """初始化服务"""
        # 获取项目根目录
        self.project_root = Path(__file__).parent.parent.parent
        self.config_dir = self.project_root / "config"
        logger.info(f"业务生成服务初始化完成，配置目录: {self.config_dir}")

    def get_story_config(self, story_id: int) -> Dict[str, Any]:
        """
        根据story_id读取配置文件

        Args:
            story_id: 故事ID

        Returns:
            配置字典

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置文件格式错误或缺少必需参数
        """
        config_path = self.config_dir / f"story_library_{story_id}.json"
        logger.info(f"读取故事配置文件: {config_path}")

        if not config_path.exists():
            error_msg = f"未找到故事配置文件: story_library_{story_id}.json"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info(f"配置文件读取成功: {config_path}")
        except json.JSONDecodeError as e:
            error_msg = f"配置文件格式错误: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 验证必需的配置项
        required_fields = ["json_db", "emo_audio_folder", "bgm_path", "script_json"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            error_msg = f"配置文件缺少必需字段: {', '.join(missing_fields)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"配置验证通过，包含字段: {list(config.keys())}")
        return config

    def get_user_audio_path(self, user_id: int, role_id: int) -> str:
        """
        从数据库查询用户的克隆声音文件路径

        Args:
            user_id: 用户ID
            role_id: 角色ID

        Returns:
            音频文件路径 (clean_input字段)

        Raises:
            ImportError: 无法导入DAO
            ValueError: 未找到用户音频记录
        """
        try:
            # 动态导入DAO，避免循环依赖
            import sys

            scripts_path = str(self.project_root / "scripts")
            if scripts_path not in sys.path:
                sys.path.insert(0, scripts_path)

            from scripts.user_input_audio_dao import UserInputAudioDAO

            logger.info(f"查询用户输入音频: user_id={user_id}, role_id={role_id}")
            dao = UserInputAudioDAO()
            record = dao.find_by_user_and_role(user_id, role_id)

            if not record:
                error_msg = "请先生成您的克隆声音"
                logger.error(
                    f"用户输入音频记录为空: user_id={user_id}, role_id={role_id}"
                )
                raise ValueError(error_msg)

            # 优先使用clean_input，如果不存在则使用init_input
            audio_path = record.get("clean_input") or record.get("init_input")

            if not audio_path:
                error_msg = "音频文件路径不存在，请重新生成克隆声音"
                logger.error(
                    f"clean_input和init_input字段均为空: user_id={user_id}, role_id={role_id}"
                )
                raise ValueError(error_msg)

            logger.info(f"成功获取用户音频路径: {audio_path}")
            return audio_path

        except ImportError as e:
            error_msg = f"无法导入数据库模块: {str(e)}"
            logger.error(error_msg)
            raise ImportError(error_msg)

    def prepare_generation_params(
        self, story_id: int, user_id: int, role_id: int, task_name: str = None
    ) -> Dict[str, Any]:
        """
        准备音频生成参数

        整合配置文件和数据库查询结果，生成完整的pipeline参数

        Args:
            story_id: 故事ID
            user_id: 用户ID
            role_id: 角色ID
            task_name: 任务名称（可选）

        Returns:
            完整的音频生成参数字典

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置错误或数据库查询失败
        """
        logger.info(
            f"准备生成参数: story_id={story_id}, user_id={user_id}, role_id={role_id}"
        )

        # 1. 读取故事配置
        try:
            config = self.get_story_config(story_id)
        except FileNotFoundError as e:
            raise FileNotFoundError("未找到故事配置")
        except ValueError as e:
            raise ValueError(f"配置文件错误: {str(e)}")

        # 2. 查询用户音频路径
        try:
            input_wav = self.get_user_audio_path(user_id, role_id)
        except ValueError as e:
            raise ValueError(str(e))
        except ImportError:
            raise ValueError("系统错误: 无法访问数据库")

        # 3. 组装参数
        params = {
            "input_wav": input_wav,
            "json_db": config["json_db"],
            "emo_audio_folder": config["emo_audio_folder"],
            "source_audio": config.get("source_audio", ""),
            "script_json": config["script_json"],
            "bgm_path": config["bgm_path"],
            "task_name": task_name or config.get("task_name", f"故事{story_id}生成"),
        }

        logger.info(f"生成参数准备完成: {params}")
        return params


# 创建全局服务实例
business_generate_service = BusinessGenerateService()
