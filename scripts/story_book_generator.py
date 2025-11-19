"""
有声故事书生成器
根据用户选择的角色和故事，结合角色的声音特点生成有声故事书
"""

import os
import sys
import json
import time
from typing import List, Dict, Optional

from scripts.user_emo_audio_dao import UserEmoAudioDAO

# 从工具模块导入TTS相关函数
from scripts.tts_utils import initialize_tts_model, TTS_AVAILABLE


class StoryBookGenerator:
    """有声故事书生成器类"""

    def __init__(self, keep_temp_files: bool = False):
        """初始化有声故事书生成器

        Args:
            keep_temp_files (bool): 是否保留临时文件，默认为False
        """
        # 初始化TTS模型
        self.tts = initialize_tts_model()
        
        # 是否保留临时文件
        self.keep_temp_files = keep_temp_files

        # 初始化DAO
        self.user_emo_audio_dao = UserEmoAudioDAO()

        # 确保输出目录存在
        self.outputs_dir = "outputs/story_books"
        os.makedirs(self.outputs_dir, exist_ok=True)

    def generate_story_book(
        self, user_id: int, role_id: int, story_path: str, keep_temp_files: Optional[bool] = None
    ) -> Optional[str]:
        """
        生成有声故事书

        Args:
            user_id (int): 用户ID
            role_id (int): 角色ID
            story_path (str): 故事文本路径
            keep_temp_files (Optional[bool]): 是否保留临时文件，如果未提供则使用实例的默认值

        Returns:
            Optional[str]: 生成的完整有声故事书路径，如果失败则返回None
        """
        if not TTS_AVAILABLE:
            print("错误: TTS 功能不可用，请确保已正确安装 indextts 包")
            return None

        if not self.tts:
            print("错误: TTS 模型未正确初始化")
            return None

        try:
            # 1. 根据user_id和role_id查询user_emo_audio表所有数据
            user_emo_audio_list = self.user_emo_audio_dao.query_by_user_role(
                user_id, role_id
            )
            if not user_emo_audio_list:
                print(f"错误: 未找到用户ID {user_id} 和角色ID {role_id} 的情绪音频数据")
                return None

            # 2. 解析故事JSON文件
            story_list = self._parse_story_file(story_path)
            if not story_list:
                print(f"错误: 无法解析故事文件 {story_path}")
                return None

            # 3. 生成单个音频片段
            audio_segments = self._generate_audio_segments(
                story_list, user_emo_audio_list
            )
            if not audio_segments:
                print("错误: 未能生成任何音频片段")
                return None

            # 4. 合并所有音频片段
            final_story_path = self._merge_audio_segments(audio_segments)

            # 5. 清理临时文件（除非设置为保留）
            # 使用传入的参数或实例默认值
            should_keep_temp_files = keep_temp_files if keep_temp_files is not None else self.keep_temp_files
            if not should_keep_temp_files:
                self._cleanup_temp_files(audio_segments)
            else:
                temp_dir = os.path.dirname(audio_segments[0]) if audio_segments else None
                if temp_dir:
                    print(f"已保留临时文件目录: {temp_dir}")

            return final_story_path

        except Exception as e:
            print(f"生成有声故事书时出错: {str(e)}")
            return None

    def _parse_story_file(self, story_path: str) -> List[Dict]:
        """
        解析故事JSON文件

        Args:
            story_path (str): 故事文件路径

        Returns:
            List[Dict]: 故事段落列表
        """
        try:
            with open(story_path, "r", encoding="utf-8") as f:
                story_data = json.load(f)
            return story_data if isinstance(story_data, list) else []
        except Exception as e:
            print(f"解析故事文件 {story_path} 时出错: {str(e)}")
            return []

    def _generate_audio_segments(
        self, story_list: List[Dict], user_emo_audio_list: List[Dict]
    ) -> List[str]:
        """
        生成音频片段

        Args:
            story_list (List[Dict]): 故事段落列表
            user_emo_audio_list (List[Dict]): 用户情绪音频数据列表

        Returns:
            List[str]: 生成的音频文件路径列表
        """
        audio_segments = []

        # 创建临时目录存放音频片段
        temp_dir = os.path.join(self.outputs_dir, f"temp_{int(time.time() * 1000)}")
        os.makedirs(temp_dir, exist_ok=True)

        for i, story_item in enumerate(story_list):
            try:
                # 提取必要字段
                text = story_item.get("text", "")
                emotion_description = story_item.get("emotion_description", "")
                interval_silence = story_item.get("interval_silence", 500)

                if not text:
                    continue

                # 根据emotion_description找到对应的用户情绪音频数据
                user_emo_audio = self._find_matching_emo_audio(
                    emotion_description, user_emo_audio_list
                )

                if not user_emo_audio:
                    print(
                        f"警告: 未找到情绪类型 '{emotion_description}' 的匹配音频数据，跳过该段落"
                    )
                    continue

                # 生成输出路径
                output_path = os.path.join(temp_dir, f"{i:04d}.wav")

                # 调用TTS生成音频
                if self.tts is not None:
                    if emotion_description == "其他":
                        # 使用平静情绪的数据
                        self.tts.infer(
                            spk_audio_prompt=user_emo_audio["spk_audio_prompt"],
                            text=text,
                            output_path=output_path,
                            emo_alpha=user_emo_audio["emo_alpha"],
                            emo_vector=user_emo_audio["emo_vector"],
                            interval_silence=interval_silence,
                            verbose=False,
                        )
                    else:
                        # 使用指定情绪的数据
                        self.tts.infer(
                            spk_audio_prompt=user_emo_audio["spk_audio_prompt"],
                            text=text,
                            emo_audio_prompt=user_emo_audio["emo_audio_prompt"],
                            output_path=output_path,
                            interval_silence=interval_silence,
                            verbose=False,
                        )
                else:
                    print("错误: TTS模型未初始化，无法生成音频")
                    continue

                audio_segments.append(output_path)
                print(f"已生成音频片段: {output_path}")

            except Exception as e:
                print(f"生成第 {i} 个音频片段时出错: {str(e)}")
                continue

        return audio_segments

    def _find_matching_emo_audio(
        self, emotion_description: str, user_emo_audio_list: List[Dict]
    ) -> Optional[Dict]:
        """
        根据情绪描述找到匹配的用户情绪音频数据

        Args:
            emotion_description (str): 情绪描述
            user_emo_audio_list (List[Dict]): 用户情绪音频数据列表

        Returns:
            Optional[Dict]: 匹配的情绪音频数据，未找到则返回None
        """
        # 如果情绪描述为"其他"，则查找"平静"类型的数据
        if emotion_description == "其他":
            for item in user_emo_audio_list:
                if item.get("emo_type") == "平静":
                    return item
        else:
            # 查找匹配的情绪类型
            for item in user_emo_audio_list:
                if item.get("emo_type") == emotion_description:
                    return item

        return None

    def _merge_audio_segments(self, audio_segments: List[str]) -> Optional[str]:
        """
        合并音频片段

        Args:
            audio_segments (List[str]): 音频片段路径列表

        Returns:
            Optional[str]: 合并后的音频文件路径
        """
        if not audio_segments:
            return None

        try:
            # 使用pydub库合并音频（如果可用）
            try:
                # 将导入放在try块内部以处理导入错误
                from pydub import AudioSegment

                # 创建一个空的音频段
                combined = AudioSegment.silent(duration=0)

                # 依次添加每个音频片段
                for segment_path in audio_segments:
                    audio = AudioSegment.from_wav(segment_path)
                    combined += audio

                # 生成最终输出路径
                timestamp_ms = int(time.time() * 1000)
                final_path = os.path.join(
                    self.outputs_dir, f"story_book_{timestamp_ms}.wav"
                )

                # 导出合并后的音频
                combined.export(final_path, format="wav")

                print(f"已生成完整有声故事书: {final_path}")
                return final_path

            except ImportError:
                print("警告: 未安装 pydub 库，无法自动合并音频")
                # 如果无法合并，返回第一个音频片段作为示例
                if audio_segments:
                    return audio_segments[0]
                return None

        except Exception as e:
            print(f"合并音频片段时出错: {str(e)}")
            return None

    def _cleanup_temp_files(self, audio_segments: List[str]):
        """
        清理临时音频文件

        Args:
            audio_segments (List[str]): 音频片段路径列表
        """
        temp_dir = os.path.dirname(audio_segments[0]) if audio_segments else None
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil

                shutil.rmtree(temp_dir)
                print(f"已清理临时文件目录: {temp_dir}")
            except Exception as e:
                print(f"清理临时文件时出错: {str(e)}")


# 示例用法
if __name__ == "__main__":
    # 创建生成器实例
    generator = StoryBookGenerator()

    # 生成有声故事书
    # final_path = generator.generate_story_book(
    #     user_id=1,
    #     role_id=1,
    #     story_path="db/xiaohongmao.json"
    # )
    # 
    # if final_path:
    #     print(f"有声故事书生成成功: {final_path}")
    # else:
    #     print("有声故事书生成失败")
