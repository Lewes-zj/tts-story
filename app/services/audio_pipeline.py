"""
音频处理流水线 (Audio Pipeline)

负责编排和执行完整的音频生成流程:
1. Voice Cloning (语音克隆)
2. Trim Silence (去除静音)
3. Build Sequence (构建序列)
4. Alignment (对齐合成)

特性:
- 基于task_id创建独立工作目录
- 使用Semaphore控制GPU并发 (最多1个任务同时执行AI推理)
- 详细的错误处理和状态追踪
"""

import os
import sys
import logging
import threading
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录到路径 (用于导入scripts模块)
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 导入重构后的脚本函数
from scripts.auto_voice_cloner import run_voice_cloning
from scripts.trim_silence_tool import run_trim_silence
from scripts.build_story_sequence import run_build_sequence
from scripts.align import run_alignment
from scripts.user_story_book_dao import UserStoryBookDAO

from app.services.task_manager import task_manager
from app.models import TaskStatus

logger = logging.getLogger(__name__)

# ============================================================================
# GPU 并发控制 (全局 Semaphore)
# ============================================================================

# 限制同时只有1个任务在执行AI推理 (防止GPU显存溢出)
gpu_semaphore = threading.Semaphore(1)


# ============================================================================
# Pipeline 编排器
# ============================================================================


def generate_audio_pipeline(task_id: str, params: Dict[str, Any]):
    """
    完整音频生成流水线

    Args:
        task_id: 任务ID
        params: 请求参数字典

    执行流程:
        Step 1: Voice Cloning (语音克隆)
        Step 2: Trim Silence (去除静音)
        Step 3: Build Sequence (构建序列)
        Step 4: Alignment (对齐合成)
    """

    # 创建任务专属工作目录
    task_dir = Path(f"data/tasks/{task_id}")
    task_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"🚀 任务开始: {task_id}")
    logger.info(f"📂 工作目录: {task_dir}")

    # 定义各步骤的输出目录
    cloned_dir = task_dir / "1_cloned"
    trimmed_dir = task_dir / "2_trimmed"
    sequence_json = task_dir / "3_sequence.json"
    final_output = task_dir / "4_final_output.wav"

    try:
        # 获取 GPU 锁 (阻塞等待，直到其他任务完成)
        logger.info(f"⏳ 等待 GPU 资源...")
        with gpu_semaphore:
            logger.info(f"✅ 已获取 GPU 资源，开始执行")

            # ================================================================
            # Step 1: Voice Cloning (语音克隆)
            # ================================================================
            task_manager.update_task(
                task_id=task_id,
                status=TaskStatus.PROCESSING,
                progress="Step 1/4: 正在执行语音克隆...",
                current_step=1,
            )

            logger.info(f"[Step 1/4] 开始语音克隆")

            try:
                result_step1 = run_voice_cloning(
                    input_wav=params["input_wav"],
                    json_db=params["json_db"],
                    output_dir=str(cloned_dir),
                    emo_audio_folder=params.get("emo_audio_folder"),
                )

                task_manager.add_step_result(
                    task_id=task_id,
                    step_number=1,
                    step_name="Voice Cloning",
                    status=TaskStatus.COMPLETED,
                    result=result_step1,
                )

                logger.info(
                    f"✅ Step 1 完成: 成功 {result_step1['success']}/{result_step1['total']}"
                )

                if result_step1["failed"] > 0:
                    logger.warning(f"⚠️ 有 {result_step1['failed']} 个音频克隆失败")

            except Exception as e:
                logger.error(f"❌ Step 1 失败: {str(e)}")
                task_manager.add_step_result(
                    task_id=task_id,
                    step_number=1,
                    step_name="Voice Cloning",
                    status=TaskStatus.FAILED,
                    error=str(e),
                )
                raise

        # GPU密集型任务完成，释放GPU资源
        logger.info(f"🔓 已释放 GPU 资源")

        # ================================================================
        # Step 2: Trim Silence (去除静音)
        # ================================================================
        task_manager.update_task(
            task_id=task_id,
            progress="Step 2/4: 正在去除静音...",
            current_step=2,
        )

        logger.info(f"[Step 2/4] 开始去除静音")

        try:
            result_step2 = run_trim_silence(
                input_dir=str(cloned_dir),
                output_dir=str(trimmed_dir),
                silence_thresh=params.get("silence_thresh", -40),
            )

            task_manager.add_step_result(
                task_id=task_id,
                step_number=2,
                step_name="Trim Silence",
                status=TaskStatus.COMPLETED,
                result=result_step2,
            )

            logger.info(
                f"✅ Step 2 完成: 处理 {result_step2['success_count']}/{result_step2['total_files']} 个文件"
            )

        except Exception as e:
            logger.error(f"❌ Step 2 失败: {str(e)}")
            task_manager.add_step_result(
                task_id=task_id,
                step_number=2,
                step_name="Trim Silence",
                status=TaskStatus.FAILED,
                error=str(e),
            )
            raise

        # ================================================================
        # Step 3: Build Sequence (构建序列)
        # ================================================================
        task_manager.update_task(
            task_id=task_id,
            progress="Step 3/4: 正在构建音频序列...",
            current_step=3,
        )

        logger.info(f"[Step 3/4] 开始构建序列")

        try:
            # 音频文件夹列表：旁白 + 对白（如果提供）
            audio_folders = [str(trimmed_dir)]
            dialogue_audio_folder = params.get("dialogue_audio_folder", "")
            if dialogue_audio_folder:
                if os.path.exists(dialogue_audio_folder):
                    audio_folders.append(dialogue_audio_folder)
                    logger.info(f"✅ Step3 已添加对白音频文件夹: {dialogue_audio_folder}")
                else:
                    logger.warning(
                        f"⚠️ Step3 对白音频文件夹不存在: {dialogue_audio_folder}"
                    )
            else:
                logger.warning("⚠️ Step3 未配置对白音频文件夹，将只使用旁白音频")

            result_step3 = run_build_sequence(
                source_audio=params["source_audio"],
                script_json=params["script_json"],
                audio_folders=audio_folders,
                output_json=str(sequence_json),
            )

            task_manager.add_step_result(
                task_id=task_id,
                step_number=3,
                step_name="Build Sequence",
                status=TaskStatus.COMPLETED,
                result=result_step3,
            )

            logger.info(
                f"✅ Step 3 完成: {result_step3['matched_clips']}/{result_step3['total_clips']} 匹配成功"
            )

        except Exception as e:
            logger.error(f"❌ Step 3 失败: {str(e)}")
            task_manager.add_step_result(
                task_id=task_id,
                step_number=3,
                step_name="Build Sequence",
                status=TaskStatus.FAILED,
                error=str(e),
            )
            raise

        # ================================================================
        # Step 4: Alignment (对齐合成)
        # ================================================================
        task_manager.update_task(
            task_id=task_id,
            progress="Step 4/4: 正在对齐合成最终音频...",
            current_step=4,
        )

        logger.info(f"[Step 4/4] 开始对齐合成")

        try:
            # 构建音频文件夹列表：包含旁白和对白两个文件夹
            audio_folders = [str(trimmed_dir)]  # 旁白音频文件夹
            
            # 如果配置中提供了对话音频文件夹，添加到列表中
            dialogue_audio_folder = params.get("dialogue_audio_folder", "")
            if dialogue_audio_folder:
                if os.path.exists(dialogue_audio_folder):
                    audio_folders.append(dialogue_audio_folder)  # 对白音频文件夹
                    logger.info(f"✅ 已添加对白音频文件夹: {dialogue_audio_folder}")
                else:
                    logger.warning(f"⚠️ 对白音频文件夹不存在: {dialogue_audio_folder}")
            else:
                logger.warning("⚠️ 未配置对白音频文件夹，将只使用旁白音频")

            result_step4 = run_alignment(
                config_json=str(sequence_json),
                audio_folders=audio_folders,
                bgm_path=params["bgm_path"],
                output_wav=str(final_output),
            )

            task_manager.add_step_result(
                task_id=task_id,
                step_number=4,
                step_name="Alignment",
                status=TaskStatus.COMPLETED,
                result=result_step4,
            )

            logger.info(f"✅ Step 4 完成: 输出文件 {final_output}")

        except Exception as e:
            logger.error(f"❌ Step 4 失败: {str(e)}")
            task_manager.add_step_result(
                task_id=task_id,
                step_number=4,
                step_name="Alignment",
                status=TaskStatus.FAILED,
                error=str(e),
            )
            raise

        # ================================================================
        # 任务成功完成
        # ================================================================
        final_result = {
            "task_dir": str(task_dir),
            "output_wav": str(final_output),
            "step1_voice_cloning": result_step1,
            "step2_trim_silence": result_step2,
            "step3_build_sequence": result_step3,
            "step4_alignment": result_step4,
        }

        # 将生成的音频路径写入用户故事书表，便于后续访问
        user_id = params.get("user_id")
        role_id = params.get("role_id")
        story_id = params.get("story_id")
        if user_id is not None and role_id is not None and story_id is not None:
            try:
                dao = UserStoryBookDAO()
                dao.insert(
                    user_id=user_id,
                    role_id=role_id,
                    story_id=story_id,
                    story_book_path=str(final_output),
                )
                logger.info("✅ 已将生成的音频路径写入 user_story_books")
            except Exception as dao_error:
                logger.error(f"❌ 写入用户故事书失败: {dao_error}")
        else:
            logger.info("ℹ️ 未提供 user_id/role_id/story_id，跳过故事书入库")

        task_manager.update_task(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            progress="✅ 任务完成！所有步骤已成功执行",
            current_step=4,
            result=final_result,
            output_wav=str(final_output),
        )

        logger.info(f"🎉 任务完成: {task_id}")
        logger.info(f"📁 最终输出: {final_output}")

    except Exception as e:
        # 任务失败
        error_message = f"任务执行失败: {str(e)}"

        # 详细记录错误信息到日志
        logger.error(f"❌ 任务失败: {task_id}")
        logger.error(f"   错误类型: {type(e).__name__}")
        logger.error(f"   错误信息: {error_message}")
        logger.error(f"   任务参数: {params}")

        # 更新任务状态为失败（短暂保留以便日志记录）
        task_manager.update_task(
            task_id=task_id,
            status=TaskStatus.FAILED,
            progress="❌ 任务失败",
            error=error_message,
        )

        # 自动删除失败的任务
        try:
            logger.info(f"🗑️ 自动删除失败任务: {task_id}")
            task_manager.delete_task(task_id)
            logger.info(f"✅ 失败任务已删除: {task_id}")
        except Exception as delete_error:
            logger.error(f"⚠️ 删除失败任务时出错: {str(delete_error)}")
