"""
业务层音频生成服务

提供基于ID的音频生成功能，自动处理配置文件读取和数据库查询
"""

import json
import logging
import os
import time
import sys
import yaml
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

        # ---------------------------------------------------------------
        # 初始化 CosyVoiceV3 客户端 (无连接池模式)
        # ---------------------------------------------------------------
        scripts_path = str(self.project_root / "scripts")
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)

        try:
            from scripts.cosyvoice_v3 import CosyVoiceV3
            
            # 直接实例化，无需 pool_size
            logger.info("正在初始化 CosyVoiceV3 客户端 (短连接模式)...")
            self.cosy_voice_client = CosyVoiceV3()
            logger.info("✓ CosyVoiceV3 客户端初始化成功")
        except Exception as e:
            logger.error(f"❌ CosyVoiceV3 初始化失败: {e}")
            self.cosy_voice_client = None

    def _load_character_audio_clone_config(self) -> Dict[str, Any]:
        """从配置文件中加载角色音频克隆配置"""
        config_path = self.config_dir / "config.yaml"
        default_config = {
            "clone_text": "小朋友们大家好，这是一段黄金母本的音频，这段音频的主要目的呀，是为后续的所有音频克隆提供一段完美的音频输入。",
            "tts2": True,
            "cosyvoice_model": "cosyvoice-v3-plus"
        }
        
        if not config_path.exists():
            return default_config
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            if config and "character_audio_clone" in config:
                clone_config = config["character_audio_clone"]
                return {
                    "clone_text": clone_config.get("clone_text", default_config["clone_text"]),
                    "tts2": clone_config.get("tts2", default_config["tts2"]),
                    "cosyvoice_model": clone_config.get("cosyvoice_model", default_config["cosyvoice_model"])
                }
            else:
                return default_config
        except Exception:
            return default_config

    def get_story_config(self, story_id: int) -> Dict[str, Any]:
        """根据story_id读取配置文件"""
        config_path = self.config_dir / f"story_library_{story_id}.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"未找到故事配置文件: story_library_{story_id}.json")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件格式错误: {str(e)}")

        required_fields = ["json_db", "emo_audio_folder", "source_audio", "script_json", "bgm_path", "dialogue_audio_folder", "task_name"]
        if any(f not in config or not config[f] for f in required_fields):
             raise ValueError("配置文件缺少必需字段")

        return config

    def _execute_voice_cloning_steps(
        self, user_id: int, role_id: int, clean_input_path: str, user_role_dir: str, base_name: str
    ) -> tuple:
        """执行 CosyVoice V3 和 AutoVoiceCloner 声音克隆"""
        try:
            from scripts.auto_voice_cloner import AutoVoiceCloner
            from scripts.user_input_audio_dao import UserInputAudioDAO
            
            user_input_audio_dao = UserInputAudioDAO()
            
            logger.info(f"🎬 [生成任务] 开始执行角色声音克隆 - User: {user_id}, Role: {role_id}")
            
            # 配置读取
            clone_config = self._load_character_audio_clone_config()
            fixed_text = clone_config["clone_text"]
            use_tts2 = clone_config["tts2"]
            
            golden_master_prompt = self.project_root / "prompt" / "golden_master_prompt.MP3"
            golden_master_prompt_str = str(golden_master_prompt)
            
            cosy_voice_path = None
            tts_voice_path = None
            
            # --- 步骤2: CosyVoice V3 ---
            logger.info("📝 [步骤2] 开始 CosyVoice V3 声音克隆")
            
            if clean_input_path and os.path.exists(clean_input_path):
                try:
                    public_base_url = os.getenv("PUBLIC_BASE_URL")
                    if public_base_url and self.cosy_voice_client:
                        clean_file_name = os.path.basename(clean_input_path)
                        audio_url = f"{public_base_url.rstrip('/')}/outputs/{user_id}/{role_id}/{clean_file_name}"
                        cosy_output_path = os.path.abspath(os.path.join(user_role_dir, f"{base_name}_cosyvoice.mp3"))
                        
                        # 重试机制 (即便没有连接池，网络抖动也需要重试)
                        max_retries = 3
                        for retry_count in range(max_retries):
                            try:
                                logger.info(f"   CosyVoice 尝试 {retry_count + 1}/{max_retries}...")
                                self.cosy_voice_client.synthesize(
                                    audio_url=audio_url,
                                    text_to_synthesize=fixed_text,
                                    output_file=cosy_output_path,
                                )
                                break
                            except Exception as e:
                                logger.warning(f"⚠️ CosyVoice 异常: {e}")
                                if retry_count < max_retries - 1:
                                    time.sleep(2.0)
                                else:
                                    logger.error("❌ CosyVoice 所有重试均失败")

                        if os.path.exists(cosy_output_path):
                            cosy_voice_path = cosy_output_path
                            user_input_audio_dao.update_cosy_voice(user_id, role_id, cosy_voice_path)
                            logger.info("✅ CosyVoice V3 成功")
                    else:
                        logger.warning("⚠️ 跳过 CosyVoice: PUBLIC_BASE_URL 未配置或客户端初始化失败")
                except Exception as e:
                    logger.error(f"❌ CosyVoice 流程异常: {e}")
            
            # --- 步骤3: AutoVoiceCloner ---
            cosy_voice_failed = cosy_voice_path is None or not os.path.exists(cosy_voice_path)
            should_run_tts2 = use_tts2 or cosy_voice_failed
            
            if should_run_tts2:
                logger.info("📝 [步骤3] 开始 AutoVoiceCloner")
                input_for_cloning = cosy_voice_path if not cosy_voice_failed else clean_input_path
                
                if input_for_cloning and os.path.exists(input_for_cloning) and os.path.exists(golden_master_prompt_str):
                    try:
                        voice_cloner = AutoVoiceCloner(output_dir=user_role_dir)
                        clone_result = voice_cloner.run_cloning(
                            input_audio=input_for_cloning,
                            emo_audio=golden_master_prompt_str,
                            emo_text=fixed_text,
                        )
                        if clone_result.get("success") > 0 and clone_result.get("results"):
                            cloned_path = clone_result["results"][0].get("output_path")
                            if cloned_path and os.path.exists(cloned_path):
                                tts_voice_path = os.path.abspath(cloned_path)
                                user_input_audio_dao.update_tts_voice(user_id, role_id, tts_voice_path)
                                logger.info("✅ AutoVoiceCloner 成功")
                    except Exception as e:
                        logger.error(f"❌ AutoVoiceCloner 异常: {e}")
            
            return cosy_voice_path, tts_voice_path
            
        except Exception as e:
            logger.error(f"💥 角色声音克隆严重错误: {e}", exc_info=True)
            return None, None

    def get_user_audio_path(self, user_id: int, role_id: int) -> str:
        """查询用户音频，必要时触发生成"""
        try:
            from scripts.user_input_audio_dao import UserInputAudioDAO
            dao = UserInputAudioDAO()
            record = dao.find_by_user_and_role(user_id, role_id)

            if not record:
                raise ValueError("请先完善角色音频录制")

            # 1. 检查现有文件
            if record.get("tts_voice") and os.path.exists(record["tts_voice"]):
                return record["tts_voice"]
            if record.get("cosy_voice") and os.path.exists(record["cosy_voice"]):
                return record["cosy_voice"]
                
            # 2. 如果没有生成过，尝试现场生成
            clean_input = record.get("clean_input")
            if clean_input and os.path.exists(clean_input):
                logger.info("⚠️ 缓存缺失，触发实时生成...")
                clean_input_path = os.path.abspath(clean_input)
                base_name = os.path.splitext(os.path.basename(clean_input_path))[0]
                
                c_path, t_path = self._execute_voice_cloning_steps(
                    user_id, role_id, clean_input_path, os.path.dirname(clean_input_path), base_name
                )
                
                if t_path and os.path.exists(t_path): return t_path
                if c_path and os.path.exists(c_path): return c_path
                raise ValueError("生成失败，未产生有效文件")
            else:
                raise ValueError("角色音频录制不完整 (clean_input 缺失)")

        except ImportError as e:
            raise ImportError(str(e))

    def prepare_generation_params(self, story_id: int, user_id: int, role_id: int, task_name: str = None) -> Dict:
        """准备参数"""
        config = self.get_story_config(story_id)
        input_wav = self.get_user_audio_path(user_id, role_id)

        return {
            "input_wav": input_wav,
            "json_db": config["json_db"],
            "emo_audio_folder": config["emo_audio_folder"],
            "source_audio": config["source_audio"],
            "script_json": config["script_json"],
            "bgm_path": config["bgm_path"],
            "dialogue_audio_folder": config["dialogue_audio_folder"],
            "task_name": task_name or config["task_name"],
            "story_id": story_id,
            "user_id": user_id,
            "role_id": role_id,
        }

business_generate_service = BusinessGenerateService()