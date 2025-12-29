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
        # [核心修复] 初始化 CosyVoiceV3 单例
        # ---------------------------------------------------------------
        # 1. 确保 scripts 目录在 python path 中，以便导入自定义模块
        scripts_path = str(self.project_root / "scripts")
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
            logger.info(f"已添加 scripts 路径到 sys.path: {scripts_path}")

        try:
            from scripts.cosyvoice_v3 import CosyVoiceV3
            
            # 2. 实例化全局唯一的客户端
            # pool_size=20 意味着我们可以同时维持 20 个长连接，足够应对高并发
            logger.info("正在初始化 CosyVoiceV3 全局单例 (启用对象池)...")
            self.cosy_voice_client = CosyVoiceV3(
                pool_size=20, 
                use_object_pool=True
            )
            logger.info("✓ CosyVoiceV3 全局单例初始化成功")
        except Exception as e:
            logger.error(f"❌ CosyVoiceV3 初始化失败: {e}")
            # 如果初始化失败，设为 None，后续逻辑需处理此情况
            self.cosy_voice_client = None

    def _load_character_audio_clone_config(self) -> Dict[str, Any]:
        """
        从配置文件中加载角色音频克隆配置
        
        Returns:
            配置字典，包含 clone_text, tts2, cosyvoice_model 等配置项
        """
        config_path = self.config_dir / "config.yaml"
        default_config = {
            "clone_text": "小朋友们大家好，这是一段黄金母本的音频，这段音频的主要目的呀，是为后续的所有音频克隆提供一段完美的音频输入。",
            "tts2": True,
            "cosyvoice_model": "cosyvoice-v3-plus"
        }
        
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
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
                logger.warning("配置文件中未找到 character_audio_clone 配置项，使用默认配置")
                return default_config
        except Exception as e:
            logger.warning(f"读取配置文件失败: {e}，使用默认配置")
            return default_config

    def get_story_config(self, story_id: int) -> Dict[str, Any]:
        """
        根据story_id读取配置文件

        Args:
            story_id: 故事ID

        Returns:
            配置字典
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
        required_fields = [
            "json_db",
            "emo_audio_folder",
            "source_audio",
            "script_json",
            "bgm_path",
            "dialogue_audio_folder",
            "task_name",
        ]
        missing_fields = [field for field in required_fields if field not in config]
        empty_fields = [
            field for field in required_fields if not config.get(field)
        ]

        if missing_fields or empty_fields:
            details = []
            if missing_fields:
                details.append(f"缺少: {', '.join(missing_fields)}")
            if empty_fields:
                details.append(f"为空: {', '.join(empty_fields)}")
            error_msg = f"配置文件缺少必需字段或字段为空 ({'; '.join(details)})"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"配置验证通过，包含字段: {list(config.keys())}")
        return config

    def _execute_voice_cloning_steps(
        self, user_id: int, role_id: int, clean_input_path: str, user_role_dir: str, base_name: str
    ) -> tuple:
        """
        执行步骤2和步骤3：CosyVoice V3 和 AutoVoiceCloner 声音克隆
        """
        try:
            # 动态导入其他脚本模块 (CosyVoiceV3 已在 init 中导入)
            # scripts_path 已在 __init__ 中添加到 sys.path
            
            from scripts.auto_voice_cloner import AutoVoiceCloner
            from scripts.user_input_audio_dao import UserInputAudioDAO
            
            user_input_audio_dao = UserInputAudioDAO()
            
            logger.info("=" * 70)
            logger.info("🎬 [生成任务] 开始执行角色声音克隆（步骤2和步骤3）")
            logger.info(f"   用户ID: {user_id}")
            logger.info(f"   角色ID: {role_id}")
            logger.info(f"   降噪音频路径: {clean_input_path}")
            logger.info("=" * 70)
            
            # 从配置文件读取克隆文本
            clone_config = self._load_character_audio_clone_config()
            fixed_text = clone_config["clone_text"]
            use_tts2 = clone_config["tts2"]
            
            # Golden Master Prompt 音频路径
            golden_master_prompt = self.project_root / "prompt" / "golden_master_prompt.MP3"
            golden_master_prompt_str = str(golden_master_prompt)
            
            cosy_voice_path = None
            tts_voice_path = None
            
            # 步骤2: 使用 CosyVoice V3 进行声音克隆
            logger.info("-" * 70)
            logger.info("📝 [步骤2] 开始 CosyVoice V3 声音克隆")
            logger.info("-" * 70)
            
            if clean_input_path and os.path.exists(clean_input_path):
                logger.info(f"✓ 降噪音频文件存在: {clean_input_path}")
                
                try:
                    public_base_url = os.getenv("PUBLIC_BASE_URL")
                    if not public_base_url:
                        logger.warning("⚠️ PUBLIC_BASE_URL 未配置，跳过 CosyVoice V3 处理")
                    elif self.cosy_voice_client is None:
                         logger.error("❌ CosyVoice 客户端未成功初始化，跳过步骤2")
                    else:
                        logger.info(f"✓ PUBLIC_BASE_URL 已配置: {public_base_url}")
                        
                        clean_file_name = os.path.basename(clean_input_path)
                        audio_url = f"{public_base_url.rstrip('/')}/outputs/{user_id}/{role_id}/{clean_file_name}"
                        logger.info(f"📡 构造音频URL: {audio_url}")
                        
                        cosy_output_path = os.path.join(user_role_dir, f"{base_name}_cosyvoice.mp3")
                        cosy_output_path = os.path.abspath(cosy_output_path)
                        
                        # 添加重试机制，处理 WebSocket 连接问题
                        max_retries = 3
                        retry_delay = 2.0
                        
                        # [核心修复] 使用 self.cosy_voice_client 而不是新建实例
                        for retry_count in range(max_retries):
                            try:
                                logger.info(f"   尝试 {retry_count + 1}/{max_retries}...")
                                self.cosy_voice_client.synthesize(
                                    audio_url=audio_url,
                                    text_to_synthesize=fixed_text,
                                    output_file=cosy_output_path,
                                )
                                logger.info("✓ CosyVoice V3 API 调用完成")
                                break
                            except (TimeoutError, Exception) as e:
                                error_msg = str(e)
                                error_type = type(e).__name__
                                logger.warning(f"⚠️ CosyVoice V3 调用异常 (尝试 {retry_count + 1}/{max_retries}): {error_type} - {error_msg}")
                                
                                if retry_count < max_retries - 1:
                                    # 如果是网络相关错误，等待后重试
                                    time.sleep(retry_delay)
                                    retry_delay *= 1.5
                                else:
                                    logger.error("❌ CosyVoice V3 所有重试均失败，将跳过")
                                    # 即使失败也不抛出异常阻断流程，而是让 tts2 兜底
                                    pass

                        if os.path.exists(cosy_output_path):
                            cosy_voice_path = cosy_output_path
                            logger.info("✅ [步骤2] CosyVoice V3 克隆成功!")
                            
                            # 更新数据库中的 cosy_voice 字段
                            update_success = user_input_audio_dao.update_cosy_voice(user_id, role_id, cosy_voice_path)
                            if update_success:
                                logger.info(f"✅ 数据库更新成功")
                        else:
                            logger.error("❌ [步骤2] CosyVoice V3 克隆失败: 输出文件不存在")
                except Exception as e:
                    logger.error(f"❌ [步骤2] CosyVoice V3 克隆异常: {e}", exc_info=True)
                    cosy_voice_path = None
            else:
                logger.warning("⚠️ [步骤2] 降噪音频不可用，跳过 CosyVoice V3 处理")

            # 步骤3: 使用 AutoVoiceCloner 进行最终声音克隆
            cosy_voice_failed = cosy_voice_path is None or not os.path.exists(cosy_voice_path)
            should_run_tts2 = use_tts2 or cosy_voice_failed
            
            if should_run_tts2:
                logger.info("-" * 70)
                logger.info("📝 [步骤3] 开始 AutoVoiceCloner 最终声音克隆")
                if cosy_voice_failed:
                    logger.info("   原因: CosyVoice V3 失败，使用 AutoVoiceCloner 作为兜底")
                
                input_for_cloning = cosy_voice_path if not cosy_voice_failed else clean_input_path
                
                if input_for_cloning and os.path.exists(input_for_cloning):
                    try:
                        if not os.path.exists(golden_master_prompt_str):
                            logger.error(f"❌ [步骤3] Golden Master Prompt 文件不存在")
                            tts_voice_path = None
                        else:
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
                                    logger.info("✅ [步骤3] AutoVoiceCloner 克隆成功!")
                                    
                                    # 更新数据库中的 tts_voice 字段
                                    update_success = user_input_audio_dao.update_tts_voice(user_id, role_id, tts_voice_path)
                                    if update_success:
                                        logger.info(f"✅ 数据库更新成功")
                                else:
                                    logger.error("❌ [步骤3] 输出文件不存在")
                            else:
                                error_msg = clone_result.get("results", [{}])[0].get("error", "未知错误")
                                logger.error(f"❌ [步骤3] 失败: {error_msg}")
                    except Exception as e:
                        logger.error(f"❌ [步骤3] 异常: {e}", exc_info=True)
                        tts_voice_path = None
                else:
                    logger.warning("⚠️ [步骤3] 输入音频不可用")
            
            # 任务完成总结
            logger.info("=" * 70)
            logger.info("🎉 [生成任务] 角色声音克隆处理完成")
            logger.info(f"   CosyVoice 输出: {cosy_voice_path if cosy_voice_path else 'N/A'}")
            logger.info(f"   TTS Voice 输出: {tts_voice_path if tts_voice_path else 'N/A'}")
            logger.info("=" * 70)
            
            return cosy_voice_path, tts_voice_path
            
        except Exception as e:
            logger.error("💥 [生成任务] 角色声音克隆处理异常", exc_info=True)
            return None, None

    def get_user_audio_path(self, user_id: int, role_id: int) -> str:
        """
        从数据库查询用户的克隆声音文件路径
        优先级：tts_voice > cosy_voice > 如果都没有则执行步骤2和步骤3
        """
        try:
            from scripts.user_input_audio_dao import UserInputAudioDAO

            logger.info(f"查询用户输入音频: user_id={user_id}, role_id={role_id}")
            dao = UserInputAudioDAO()
            record = dao.find_by_user_and_role(user_id, role_id)

            if not record:
                error_msg = "请先完善角色音频录制"
                logger.error(f"用户输入音频记录为空: user_id={user_id}, role_id={role_id}")
                raise ValueError(error_msg)

            # 优先使用 tts_voice
            tts_voice = record.get("tts_voice")
            if tts_voice and os.path.exists(tts_voice):
                logger.info(f"使用 tts_voice 字段: {tts_voice}")
                return tts_voice
            
            # 其次使用 cosy_voice
            cosy_voice = record.get("cosy_voice")
            if cosy_voice and os.path.exists(cosy_voice):
                logger.info(f"使用 cosy_voice 字段: {cosy_voice}")
                return cosy_voice
                
            # 如果都没有，执行生成流程
            clean_input = record.get("clean_input")
            if clean_input and os.path.exists(clean_input):
                logger.info("⚠️ 现有克隆音频缺失，开始执行实时生成...")
                
                clean_input_path = os.path.abspath(clean_input)
                user_role_dir = os.path.dirname(clean_input_path)
                base_name = os.path.splitext(os.path.basename(clean_input_path))[0]
                
                cosy_voice_path, tts_voice_path = self._execute_voice_cloning_steps(
                    user_id=user_id,
                    role_id=role_id,
                    clean_input_path=clean_input_path,
                    user_role_dir=user_role_dir,
                    base_name=base_name
                )
                
                # 重新查询获取最新路径
                record = dao.find_by_user_and_role(user_id, role_id)
                tts_voice = record.get("tts_voice") if record else None
                cosy_voice = record.get("cosy_voice") if record else None
                
                if tts_voice and os.path.exists(tts_voice):
                    return tts_voice
                elif cosy_voice and os.path.exists(cosy_voice):
                    return cosy_voice
                else:
                    raise ValueError("角色音频克隆失败，未生成有效音频文件")
            else:
                raise ValueError("角色音频录制不完整 (clean_input 缺失)")

        except ImportError as e:
            logger.error(f"无法导入数据库模块: {e}")
            raise ImportError(str(e))

    def prepare_generation_params(
        self, story_id: int, user_id: int, role_id: int, task_name: str = None
    ) -> Dict[str, Any]:
        """
        准备音频生成参数
        """
        logger.info(f"准备生成参数: story_id={story_id}, user_id={user_id}, role_id={role_id}")

        config = self.get_story_config(story_id)
        input_wav = self.get_user_audio_path(user_id, role_id)

        params = {
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

        logger.info(f"生成参数准备完成")
        return params


# 创建全局服务实例
business_generate_service = BusinessGenerateService()