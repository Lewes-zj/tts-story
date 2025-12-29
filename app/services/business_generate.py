"""
业务层音频生成服务

提供基于ID的音频生成功能，自动处理配置文件读取和数据库查询
"""

import json
import logging
import os
import time
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

        # 验证必需的配置项（全部必填且不能为空）
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
        
        Args:
            user_id: 用户ID
            role_id: 角色ID
            clean_input_path: 降噪后的音频文件路径
            user_role_dir: 用户角色目录
            base_name: 文件基础名称（不含扩展名）
            
        Returns:
            (cosy_voice_path, tts_voice_path) 元组
        """
        try:
            # 动态导入所需模块
            import sys
            scripts_path = str(self.project_root / "scripts")
            if scripts_path not in sys.path:
                sys.path.insert(0, scripts_path)
            
            from scripts.cosyvoice_v3 import CosyVoiceV3
            from scripts.auto_voice_cloner import AutoVoiceCloner
            from scripts.user_input_audio_dao import UserInputAudioDAO
            
            user_input_audio_dao = UserInputAudioDAO()
            
            logger.info("=" * 70)
            logger.info("🎬 [生成任务] 开始执行角色声音克隆（步骤2和步骤3）")
            logger.info(f"   用户ID: {user_id}")
            logger.info(f"   角色ID: {role_id}")
            logger.info(f"   降噪音频路径: {clean_input_path}")
            logger.info(f"   工作目录: {user_role_dir}")
            logger.info("=" * 70)
            
            # 从配置文件读取克隆文本
            clone_config = self._load_character_audio_clone_config()
            fixed_text = clone_config["clone_text"]
            use_tts2 = clone_config["tts2"]
            logger.info(f"📋 克隆文本（从配置文件读取）: {fixed_text}")
            logger.info(f"📋 TTS2 配置（从配置文件读取）: {use_tts2}")
            
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
                file_size = os.path.getsize(clean_input_path)
                logger.info(f"  文件大小: {file_size} bytes")
                
                try:
                    public_base_url = os.getenv("PUBLIC_BASE_URL")
                    if not public_base_url:
                        logger.warning("⚠️ PUBLIC_BASE_URL 未配置，跳过 CosyVoice V3 处理")
                    else:
                        logger.info(f"✓ PUBLIC_BASE_URL 已配置: {public_base_url}")
                        
                        # 等待一段时间，确保文件系统完全同步
                        # logger.info("⏳ 等待文件系统完全同步（10秒）...")
                        # time.sleep(10.0)
                        # logger.info("✓ 文件系统同步等待完成")
                        
                        clean_file_name = os.path.basename(clean_input_path)
                        audio_url = f"{public_base_url.rstrip('/')}/outputs/{user_id}/{role_id}/{clean_file_name}"
                        logger.info(f"📡 构造音频URL: {audio_url}")
                        
                        cosy_output_path = os.path.join(user_role_dir, f"{base_name}_cosyvoice.mp3")
                        cosy_output_path = os.path.abspath(cosy_output_path)
                        logger.info(f"📁 输出文件路径: {cosy_output_path}")

                        logger.info("🔄 正在调用 CosyVoice V3 API 进行声音克隆...")
                        
                        # 添加重试机制，处理 WebSocket 连接问题
                        max_retries = 3
                        retry_delay = 5.0
                        cosy_voice_client = CosyVoiceV3()
                        
                        for retry_count in range(max_retries):
                            try:
                                logger.info(f"   尝试 {retry_count + 1}/{max_retries}...")
                                cosy_voice_client.synthesize(
                                    audio_url=audio_url,
                                    text_to_synthesize=fixed_text,
                                    output_file=cosy_output_path,
                                )
                                logger.info("✓ CosyVoice V3 API 调用完成")
                                break
                            except (TimeoutError, Exception) as e:
                                error_msg = str(e)
                                error_type = type(e).__name__
                                logger.warning(f"⚠️ CosyVoice V3 调用异常 (尝试 {retry_count + 1}/{max_retries}): {error_type}")
                                logger.warning(f"   错误信息: {error_msg}")
                                
                                if retry_count < max_retries - 1:
                                    if "websocket" in error_msg.lower() or "connection" in error_msg.lower() or isinstance(e, TimeoutError):
                                        logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                                        time.sleep(retry_delay)
                                        retry_delay *= 1.5
                                    else:
                                        # 其他类型的错误，直接抛出
                                        raise
                                else:
                                    logger.error("❌ CosyVoice V3 所有重试均失败")
                                    logger.error("   将跳过步骤2，直接使用降噪音频进行步骤3")
                                    raise

                        if os.path.exists(cosy_output_path):
                            cosy_voice_path = cosy_output_path
                            output_size = os.path.getsize(cosy_output_path)
                            logger.info("✅ [步骤2] CosyVoice V3 克隆成功!")
                            logger.info(f"   输出文件: {cosy_voice_path}")
                            logger.info(f"   文件大小: {output_size} bytes")
                            
                            # 更新数据库中的 cosy_voice 字段
                            logger.info("💾 正在更新数据库 cosy_voice 字段...")
                            update_success = user_input_audio_dao.update_cosy_voice(user_id, role_id, cosy_voice_path)
                            if update_success:
                                logger.info(f"✅ 数据库更新成功: cosy_voice={cosy_voice_path}")
                            else:
                                logger.warning("⚠️ 数据库更新失败，但文件已生成")
                        else:
                            logger.error("❌ [步骤2] CosyVoice V3 克隆失败: 输出文件不存在")
                except Exception as e:
                    error_type = type(e).__name__
                    error_msg = str(e)
                    logger.error("❌ [步骤2] CosyVoice V3 克隆异常")
                    logger.error(f"   异常类型: {error_type}")
                    logger.error(f"   错误信息: {error_msg}")
                    logger.error("   将跳过步骤2，直接使用降噪音频进行步骤3")
                    cosy_voice_path = None
            else:
                logger.warning("⚠️ [步骤2] 降噪音频不可用，跳过 CosyVoice V3 处理")

            # 步骤3: 使用 AutoVoiceCloner 进行最终声音克隆
            # 判断是否需要执行步骤3：
            # 1. 如果配置文件中 tts2 为 true，则执行步骤3
            # 2. 如果 CosyVoice V3 失败（cosy_voice_path 为 None），无论配置如何都要执行步骤3作为兜底
            cosy_voice_failed = cosy_voice_path is None or not os.path.exists(cosy_voice_path)
            should_run_tts2 = use_tts2 or cosy_voice_failed
            
            if should_run_tts2:
                logger.info("-" * 70)
                logger.info("📝 [步骤3] 开始 AutoVoiceCloner 最终声音克隆")
                if cosy_voice_failed:
                    logger.info("   原因: CosyVoice V3 失败，使用 AutoVoiceCloner 作为兜底")
                else:
                    logger.info(f"   原因: 配置文件 tts2={use_tts2}")
                logger.info("-" * 70)
            else:
                logger.info("-" * 70)
                logger.info("📝 [步骤3] 跳过 AutoVoiceCloner 最终声音克隆")
                logger.info(f"   原因: 配置文件 tts2={use_tts2}，且 CosyVoice V3 成功")
                logger.info("-" * 70)
            
            if should_run_tts2:
                input_for_cloning = cosy_voice_path if cosy_voice_path and os.path.exists(cosy_voice_path) else clean_input_path
                logger.info(f"📥 选择输入音频: {input_for_cloning}")
                logger.info(f"   来源: {'CosyVoice V3 输出' if cosy_voice_path and os.path.exists(cosy_voice_path) else '降噪音频'}")

            if should_run_tts2 and input_for_cloning and os.path.exists(input_for_cloning):
                logger.info(f"✓ 输入音频文件存在: {input_for_cloning}")
                input_size = os.path.getsize(input_for_cloning)
                logger.info(f"  文件大小: {input_size} bytes")
                
                try:
                    if not os.path.exists(golden_master_prompt_str):
                        logger.error(f"❌ [步骤3] Golden Master Prompt 文件不存在: {golden_master_prompt_str}")
                        tts_voice_path = None
                    else:
                        logger.info(f"✓ Golden Master Prompt 文件存在: {golden_master_prompt_str}")
                        logger.info("🔄 正在调用 AutoVoiceCloner 进行声音克隆...")
                        
                        voice_cloner = AutoVoiceCloner(output_dir=user_role_dir)
                        clone_result = voice_cloner.run_cloning(
                            input_audio=input_for_cloning,
                            emo_audio=golden_master_prompt_str,
                            emo_text=fixed_text,
                        )
                        logger.info("✓ AutoVoiceCloner API 调用完成")

                        if clone_result.get("success") > 0 and clone_result.get("results"):
                            cloned_path = clone_result["results"][0].get("output_path")
                            if cloned_path and os.path.exists(cloned_path):
                                tts_voice_path = os.path.abspath(cloned_path)
                                output_size = os.path.getsize(tts_voice_path)
                                logger.info("✅ [步骤3] AutoVoiceCloner 克隆成功!")
                                logger.info(f"   输出文件: {tts_voice_path}")
                                logger.info(f"   文件大小: {output_size} bytes")
                                
                                # 更新数据库中的 tts_voice 字段
                                logger.info("💾 正在更新数据库 tts_voice 字段...")
                                update_success = user_input_audio_dao.update_tts_voice(user_id, role_id, tts_voice_path)
                                if update_success:
                                    logger.info(f"✅ 数据库更新成功: tts_voice={tts_voice_path}")
                                else:
                                    logger.warning("⚠️ 数据库更新失败，但文件已生成")
                            else:
                                logger.error("❌ [步骤3] AutoVoiceCloner 克隆失败: 输出文件不存在")
                                logger.error(f"   预期路径: {cloned_path}")
                        else:
                            error_msg = clone_result.get("results", [{}])[0].get("error", "未知错误")
                            logger.error(f"❌ [步骤3] AutoVoiceCloner 克隆失败: {error_msg}")
                except Exception as e:
                    logger.error(f"❌ [步骤3] AutoVoiceCloner 克隆异常: {str(e)}", exc_info=True)
                    tts_voice_path = None
            elif should_run_tts2:
                logger.warning("⚠️ [步骤3] 输入音频不可用，跳过 AutoVoiceCloner 处理")
            
            # 任务完成总结
            logger.info("=" * 70)
            logger.info("🎉 [生成任务] 角色声音克隆处理完成")
            logger.info(f"   用户ID: {user_id}")
            logger.info(f"   角色ID: {role_id}")
            logger.info(f"   步骤2 (CosyVoice V3): {'✅ 成功' if cosy_voice_path else '❌ 失败'}")
            logger.info(f"   步骤3 (AutoVoiceCloner): {'✅ 成功' if tts_voice_path else '❌ 失败'}")
            if cosy_voice_path:
                logger.info(f"   CosyVoice 输出: {cosy_voice_path}")
            if tts_voice_path:
                logger.info(f"   TTS Voice 输出: {tts_voice_path}")
            logger.info("=" * 70)
            
            return cosy_voice_path, tts_voice_path
            
        except Exception as e:
            logger.error("=" * 70)
            logger.error("💥 [生成任务] 角色声音克隆处理异常")
            logger.error(f"   用户ID: {user_id}")
            logger.error(f"   角色ID: {role_id}")
            logger.error(f"   异常信息: {str(e)}")
            logger.error("=" * 70, exc_info=True)
            return None, None

    def get_user_audio_path(self, user_id: int, role_id: int) -> str:
        """
        从数据库查询用户的克隆声音文件路径

        优先级：tts_voice > cosy_voice > 如果都没有则执行步骤2和步骤3

        Args:
            user_id: 用户ID
            role_id: 角色ID

        Returns:
            音频文件路径（优先使用 tts_voice，其次 cosy_voice）

        Raises:
            ImportError: 无法导入DAO
            ValueError: 未找到用户音频记录或音频文件路径不存在
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
                error_msg = "请先完善角色音频录制"
                logger.error(
                    f"用户输入音频记录为空: user_id={user_id}, role_id={role_id}"
                )
                raise ValueError(error_msg)

            # 优先级：tts_voice > cosy_voice
            audio_path = None
            field_used = None

            # 优先使用 tts_voice 字段
            tts_voice = record.get("tts_voice")
            if tts_voice and os.path.exists(tts_voice):
                audio_path = tts_voice
                field_used = "tts_voice"
                logger.info(f"使用 tts_voice 字段: {audio_path}")
            else:
                # 降级使用 cosy_voice 字段
                cosy_voice = record.get("cosy_voice")
                if cosy_voice and os.path.exists(cosy_voice):
                    audio_path = cosy_voice
                    field_used = "cosy_voice"
                    logger.info(f"使用 cosy_voice 字段: {audio_path}")
                else:
                    # 如果都没有值，先执行步骤2和步骤3
                    clean_input = record.get("clean_input")
                    if clean_input and os.path.exists(clean_input):
                        logger.info("⚠️ cosy_voice 和 tts_voice 都为空，但 clean_input 存在")
                        logger.info("   开始执行步骤2和步骤3：CosyVoice V3 和 AutoVoiceCloner 声音克隆")
                        
                        # 计算用户角色目录和基础文件名
                        clean_input_path = os.path.abspath(clean_input)
                        user_role_dir = os.path.dirname(clean_input_path)
                        base_name = os.path.splitext(os.path.basename(clean_input_path))[0]
                        
                        # 执行步骤2和步骤3
                        cosy_voice_path, tts_voice_path = self._execute_voice_cloning_steps(
                            user_id=user_id,
                            role_id=role_id,
                            clean_input_path=clean_input_path,
                            user_role_dir=user_role_dir,
                            base_name=base_name
                        )
                        
                        # 重新查询数据库，获取更新后的路径
                        record = dao.find_by_user_and_role(user_id, role_id)
                        tts_voice = record.get("tts_voice") if record else None
                        cosy_voice = record.get("cosy_voice") if record else None
                        
                        # 优先使用新生成的 tts_voice
                        if tts_voice and os.path.exists(tts_voice):
                            audio_path = tts_voice
                            field_used = "tts_voice"
                            logger.info(f"✅ 步骤2和步骤3执行完成，使用 tts_voice 字段: {audio_path}")
                        elif cosy_voice and os.path.exists(cosy_voice):
                            audio_path = cosy_voice
                            field_used = "cosy_voice"
                            logger.info(f"✅ 步骤2执行完成，使用 cosy_voice 字段: {audio_path}")
                        else:
                            error_msg = "角色音频克隆失败，步骤2和步骤3执行后仍未生成有效音频文件"
                            logger.error(
                                f"用户音频克隆失败: user_id={user_id}, role_id={role_id}, "
                                f"tts_voice={tts_voice}, cosy_voice={cosy_voice}"
                            )
                            raise ValueError(error_msg)
                    else:
                        # 如果 clean_input 也不存在，不允许生成
                        error_msg = "角色音频录制不完整，请先完善角色音频录制后再生成"
                        logger.error(
                            f"用户音频路径不存在: user_id={user_id}, role_id={role_id}, "
                            f"tts_voice={tts_voice}, cosy_voice={cosy_voice}, clean_input={clean_input}"
                        )
                        raise ValueError(error_msg)

            logger.info(f"成功获取用户音频路径 ({field_used}): {audio_path}")
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
        except FileNotFoundError:
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
            "source_audio": config["source_audio"],
            "script_json": config["script_json"],
            "bgm_path": config["bgm_path"],
            "dialogue_audio_folder": config["dialogue_audio_folder"],
            "task_name": task_name or config["task_name"],
            # 传递上下文信息，便于后续持久化入库
            "story_id": story_id,
            "user_id": user_id,
            "role_id": role_id,
        }

        logger.info(f"生成参数准备完成: {params}")
        return params


# 创建全局服务实例
business_generate_service = BusinessGenerateService()
