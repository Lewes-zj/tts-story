"""
示例：如何将 IndexTTS2VoiceCloner 集成到 StoryBookGenerator 中

这个文件展示了如何重构 StoryBookGenerator 以使用新的 IndexTTS2VoiceCloner 类。
原有的代码直接调用 tts.infer()，现在我们使用封装好的克隆器类。
"""

import os
import sys
import json
import time
import logging
from typing import List, Dict, Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from scripts.user_emo_audio_dao import UserEmoAudioDAO
from scripts.index_tts2_voice_cloner import IndexTTS2VoiceCloner, VoiceCloneParams


class StoryBookGeneratorV2:
    """
    有声故事书生成器 V2（使用 IndexTTS2VoiceCloner）

    相比原版的改进：
    1. 使用封装好的 IndexTTS2VoiceCloner 类，代码更简洁
    2. 更好的错误处理和日志记录
    3. 类型安全的参数传递
    4. 更容易维护和测试
    """

    def __init__(self, keep_temp_files: bool = False):
        """初始化有声故事书生成器

        Args:
            keep_temp_files (bool): 是否保留临时文件，默认为False
        """
        # 使用新的声音克隆器
        self.voice_cloner = IndexTTS2VoiceCloner()

        # 是否保留临时文件
        self.keep_temp_files = keep_temp_files

        # 初始化DAO
        self.user_emo_audio_dao = UserEmoAudioDAO()

        # 确保输出目录存在
        self.outputs_dir = "outputs/story_books"
        os.makedirs(self.outputs_dir, exist_ok=True)

    def generate_story_book(
        self,
        user_id: int,
        role_id: int,
        story_path: str,
        keep_temp_files: Optional[bool] = None,
    ) -> Optional[str]:
        """
        生成有声故事书

        Args:
            user_id (int): 用户ID
            role_id (int): 角色ID
            story_path (str): 故事文本路径
            keep_temp_files (Optional[bool]): 是否保留临时文件

        Returns:
            Optional[str]: 生成的完整有声故事书路径，如果失败则返回None
        """
        try:
            # 1. 查询用户情绪音频数据
            user_emo_audio_map = self.user_emo_audio_dao.query_by_user_role_as_map(
                user_id, role_id
            )
            if not user_emo_audio_map:
                logger.error(
                    f"未找到用户ID {user_id} 和角色ID {role_id} 的情绪音频数据"
                )
                return None

            # 2. 解析故事JSON文件
            story_list = self._parse_story_file(story_path)
            if not story_list:
                logger.error(f"无法解析故事文件 {story_path}")
                return None

            # 3. 生成音频片段（使用新的克隆器）
            audio_segments, interval_silence_list = self._generate_audio_segments_v2(
                story_list, user_emo_audio_map
            )

            if not audio_segments:
                logger.error("未能生成任何音频片段")
                return None

            # 4. 合并所有音频片段
            final_story_path = self._merge_audio_segments(
                audio_segments, interval_silence_list
            )

            # 5. 清理临时文件
            should_keep_temp_files = (
                keep_temp_files if keep_temp_files is not None else self.keep_temp_files
            )
            if not should_keep_temp_files:
                self._cleanup_temp_files(audio_segments)
            else:
                temp_dir = (
                    os.path.dirname(audio_segments[0]) if audio_segments else None
                )
                if temp_dir:
                    logger.info(f"已保留临时文件目录: {temp_dir}")

            return final_story_path

        except Exception as e:
            logger.error(f"生成有声故事书时出错: {str(e)}")
            return None

    def _parse_story_file(self, story_path: str) -> List[Dict]:
        """解析故事JSON文件"""
        try:
            with open(story_path, "r", encoding="utf-8") as f:
                story_data = json.load(f)
            return story_data if isinstance(story_data, list) else []
        except Exception as e:
            logger.error(f"解析故事文件 {story_path} 时出错: {str(e)}")
            return []

    def _generate_audio_segments_v2(
        self, story_list: List[Dict], user_emo_audio_map: Dict[str, Dict]
    ) -> tuple[List[str], List[int]]:
        """
        生成音频片段（V2版本 - 使用 IndexTTS2VoiceCloner）

        这是使用新克隆器类的版本，相比原版更简洁清晰。

        Args:
            story_list (List[Dict]): 故事段落列表
            user_emo_audio_map (Dict[str, Dict]): 用户情绪音频数据映射

        Returns:
            tuple[List[str], List[int]]: (音频文件路径列表, 静音间隔列表)
        """
        audio_segments = []
        interval_silence_list = []

        # 创建临时目录存放音频片段
        temp_dir = os.path.join(self.outputs_dir, f"temp_{int(time.time() * 1000)}")
        os.makedirs(temp_dir, exist_ok=True)

        # 准备批量生成参数
        batch_params = []

        for i, story_item in enumerate(story_list):
            try:
                # 提取必要字段
                text = story_item.get("text", "")
                emotion_description = story_item.get("emotion_description", "其他")
                interval_silence = story_item.get("interval_silence", 200)
                interval_silence_list.append(interval_silence)

                if not text:
                    continue

                # 根据emotion_description查找对应的用户情绪音频数据
                user_emo_audio = None
                if emotion_description == "其他":
                    user_emo_audio = user_emo_audio_map.get("平静")
                else:
                    user_emo_audio = user_emo_audio_map.get(emotion_description)

                if not user_emo_audio:
                    logger.warning(
                        f"未找到情绪类型 '{emotion_description}' 的匹配音频数据，跳过该段落"
                    )
                    continue

                # 生成输出路径
                output_path = os.path.join(temp_dir, f"{i:04d}.wav")

                # 🎯 关键改进：使用 VoiceCloneParams 构建参数
                if emotion_description == "其他":
                    # 使用情感向量模式
                    params = VoiceCloneParams(
                        text=text,
                        spk_audio_prompt=user_emo_audio["spk_audio_prompt"],
                        emo_alpha=float(user_emo_audio["emo_alpha"]),
                        emo_vector=user_emo_audio["emo_vector"],
                        output_path=output_path,
                        verbose=True,
                    )
                else:
                    # 使用情感参考音频模式
                    params = VoiceCloneParams(
                        text=text,
                        spk_audio_prompt=user_emo_audio["spk_audio_prompt"],
                        emo_audio_prompt=user_emo_audio["emo_audio_prompt"],
                        output_path=output_path,
                        verbose=True,
                    )

                batch_params.append((i, params, text))

            except Exception as e:
                logger.error(f"准备第 {i} 个音频片段参数时出错: {str(e)}")
                continue

        # 🎯 可以选择批量处理或逐个处理
        # 方式1：逐个处理（更稳定，便于调试）
        for i, params, text in batch_params:
            result = self.voice_cloner.clone(params)

            if result.success:
                audio_segments.append(result.output_path)
                logger.info(
                    f"✅ 片段 {i}: '{text[:30]}...' 已生成 ({result.duration_ms}ms)"
                )
            else:
                logger.error(f"❌ 片段 {i} 生成失败: {result.error_message}")

        # 方式2：真正的批量处理（更快，但调试困难）
        # params_only = [params for _, params, _ in batch_params]
        # results = self.voice_cloner.clone_batch(params_only)
        # for (i, _, text), result in zip(batch_params, results):
        #     if result.success:
        #         audio_segments.append(result.output_path)
        #         logger.info(f"✅ 片段 {i}: '{text[:30]}...' 已生成")

        return audio_segments, interval_silence_list

    def _merge_audio_segments(
        self, audio_segments: List[str], interval_silence_list: List[int]
    ) -> Optional[str]:
        """合并音频片段"""
        if not audio_segments:
            return None

        try:
            from pydub import AudioSegment

            combined = AudioSegment.silent(duration=0)

            for i, segment_path in enumerate(audio_segments):
                audio = AudioSegment.from_wav(segment_path)
                audio = audio.fade_in(10).fade_out(10)
                combined += audio

                if i < len(audio_segments) - 1:
                    interval_silence = (
                        interval_silence_list[i]
                        if i < len(interval_silence_list)
                        else 200
                    )
                    silence = AudioSegment.silent(duration=interval_silence)
                    combined += silence

            timestamp_ms = int(time.time() * 1000)
            final_path = os.path.join(
                self.outputs_dir, f"story_book_{timestamp_ms}.wav"
            )
            combined.export(final_path, format="wav")

            logger.info(f"✅ 已生成完整有声故事书: {final_path}")
            return final_path

        except ImportError:
            logger.warning("未安装 pydub 库，无法自动合并音频")
            return audio_segments[0] if audio_segments else None
        except Exception as e:
            logger.error(f"合并音频片段时出错: {str(e)}")
            return None

    def _cleanup_temp_files(self, audio_segments: List[str]):
        """清理临时音频文件"""
        temp_dir = os.path.dirname(audio_segments[0]) if audio_segments else None
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil

                shutil.rmtree(temp_dir)
                logger.info(f"已清理临时文件目录: {temp_dir}")
            except Exception as e:
                logger.error(f"清理临时文件时出错: {str(e)}")


# ============================================================================
# 对比示例：展示新旧代码的差异
# ============================================================================


def comparison_old_vs_new():
    """
    对比旧版和新版代码
    """

    print("=" * 70)
    print("旧版代码（直接调用 tts.infer）")
    print("=" * 70)
    print("""
    # 旧版：代码冗长，参数散乱
    self.tts.infer(
        spk_audio_prompt=user_emo_audio["spk_audio_prompt"],
        text=text,
        emo_audio_prompt=user_emo_audio["emo_audio_prompt"],
        output_path=output_path,
        verbose=True,
    )
    
    # 问题：
    # 1. 没有错误处理
    # 2. 没有返回值检查
    # 3. 参数类型不安全
    # 4. 难以测试和维护
    """)

    print("\n" + "=" * 70)
    print("新版代码（使用 IndexTTS2VoiceCloner）")
    print("=" * 70)
    print("""
    # 新版：简洁清晰，类型安全
    params = VoiceCloneParams(
        text=text,
        spk_audio_prompt=user_emo_audio["spk_audio_prompt"],
        emo_audio_prompt=user_emo_audio["emo_audio_prompt"],
        output_path=output_path,
        verbose=True
    )
    
    result = self.voice_cloner.clone(params)
    
    if result.success:
        audio_segments.append(result.output_path)
        logger.info(f"✅ 生成成功: {result.output_path}")
    else:
        logger.error(f"❌ 生成失败: {result.error_message}")
    
    # 优势：
    # 1. 参数验证自动完成
    # 2. 错误处理完善
    # 3. 返回值明确（CloneResult）
    # 4. 代码可读性强
    # 5. 易于测试
    """)


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    # 显示对比
    comparison_old_vs_new()

    print("\n" + "=" * 70)
    print("实际使用示例")
    print("=" * 70)

    # 创建生成器实例（V2版本）
    generator = StoryBookGeneratorV2(keep_temp_files=True)

    # 生成有声故事书
    # final_path = generator.generate_story_book(
    #     user_id=1,
    #     role_id=1,
    #     story_path="db/xiaohongmao.json"
    # )
    #
    # if final_path:
    #     print(f"✅ 有声故事书生成成功: {final_path}")
    # else:
    #     print("❌ 有声故事书生成失败")

    print("\n提示：取消注释上面的代码以运行实际生成任务")
