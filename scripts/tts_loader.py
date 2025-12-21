#!/usr/bin/env python3
"""
TTS 音频加载工具类
功能：封装 align.py 中的 load_all_tts 方法，提供简洁的 API 接口

用法：
    from tts_loader import TTSLoader

    loader = TTSLoader(
        config_path="config/align_config.json",
        tts_folder="tts音频积木",
        output_folder="output"
    )

    # 加载所有 TTS 音频
    success = loader.load_tts()

    # 获取加载结果
    if success:
        clips = loader.get_clips()
        for clip in clips:
            print(f"ID {clip.id}: {clip.text}, 时长={clip.duration:.2f}秒")

    # 导出音频片段到指定文件夹
    loader.export_clips()
"""

import os
import sys
import logging
from typing import List, Optional

from audio_core import AudioClip, load_config, load_all_tts

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class TTSLoader:
    """TTS 音频加载工具类"""

    def __init__(
        self,
        config_path: str,
        tts_folder: str,
        output_folder: Optional[str] = None,
    ):
        """
        初始化 TTS 加载器

        Args:
            config_path: 配置文件路径 (.json 或 .xlsx)
            tts_folder: TTS 音频文件夹路径
            output_folder: 输出文件夹路径（可选，用于导出音频片段）
        """
        self.config_path = config_path
        self.tts_folder = tts_folder
        self.output_folder = output_folder or "output"
        self.clips: List[AudioClip] = []
        self._loaded = False

        # 验证路径
        self._validate_paths()

    def _validate_paths(self) -> None:
        """验证输入路径是否存在"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        if not os.path.exists(self.tts_folder):
            raise FileNotFoundError(f"TTS 文件夹不存在: {self.tts_folder}")

        # 确保输出文件夹存在
        os.makedirs(self.output_folder, exist_ok=True)
        logger.info(f"输出文件夹: {self.output_folder}")

    def load_tts(self) -> bool:
        """
        加载所有 TTS 音频

        Returns:
            bool: 如果所有音频加载成功返回 True，否则返回 False
        """
        logger.info("=" * 60)
        logger.info("开始加载 TTS 音频")
        logger.info("=" * 60)
        logger.info(f"配置文件: {self.config_path}")
        logger.info(f"TTS 文件夹: {self.tts_folder}")

        # 1. 加载配置文件
        try:
            self.clips = load_config(self.config_path)
            logger.info(f"成功加载 {len(self.clips)} 个音频配置")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return False

        # 2. 加载所有 TTS 音频
        try:
            success = load_all_tts(self.clips, self.tts_folder)
            if success:
                self._loaded = True
                logger.info("=" * 60)
                logger.info(f"✅ 所有 TTS 音频加载成功！共 {len(self.clips)} 个片段")
                logger.info("=" * 60)
            else:
                logger.error("❌ 部分 TTS 音频加载失败，请检查日志")
            return success
        except Exception as e:
            logger.error(f"加载 TTS 音频时发生错误: {e}")
            return False

    def get_clips(self) -> List[AudioClip]:
        """
        获取所有音频片段

        Returns:
            List[AudioClip]: 音频片段列表
        """
        if not self._loaded:
            logger.warning("尚未加载音频，请先调用 load_tts() 方法")
        return self.clips

    def get_clip_by_id(self, clip_id: int) -> Optional[AudioClip]:
        """
        根据 ID 获取单个音频片段

        Args:
            clip_id: 片段 ID

        Returns:
            Optional[AudioClip]: 找到的音频片段，如果不存在则返回 None
        """
        for clip in self.clips:
            if clip.id == clip_id:
                return clip
        return None

    def get_total_duration(self) -> float:
        """
        获取所有音频片段的总时长

        Returns:
            float: 总时长（秒）
        """
        return sum(clip.duration for clip in self.clips)

    def export_clips(self, format: str = "wav") -> None:
        """
        导出所有音频片段到输出文件夹

        Args:
            format: 导出格式，默认为 'wav'
        """
        if not self._loaded:
            logger.error("尚未加载音频，无法导出")
            return

        logger.info(f"开始导出音频片段到: {self.output_folder}")

        export_count = 0
        for clip in self.clips:
            if clip.audio is None:
                logger.warning(f"跳过 ID={clip.id}，音频数据为空")
                continue

            # 生成输出文件名
            filename = f"{clip.id}_{clip.clip_type.lower()}.{format}"
            output_path = os.path.join(self.output_folder, filename)

            try:
                clip.audio.export(output_path, format=format)
                logger.info(f"导出: {filename} ({clip.duration:.2f}s)")
                export_count += 1
            except Exception as e:
                logger.error(f"导出 ID={clip.id} 失败: {e}")

        logger.info(f"共导出 {export_count}/{len(self.clips)} 个音频片段")

    def export_clip_by_id(
        self, clip_id: int, output_path: str, format: str = "wav"
    ) -> bool:
        """
        根据 ID 导出单个音频片段

        Args:
            clip_id: 片段 ID
            output_path: 输出文件路径
            format: 导出格式，默认为 'wav'

        Returns:
            bool: 导出成功返回 True，否则返回 False
        """
        clip = self.get_clip_by_id(clip_id)
        if clip is None:
            logger.error(f"未找到 ID={clip_id} 的音频片段")
            return False

        if clip.audio is None:
            logger.error(f"ID={clip_id} 的音频数据为空")
            return False

        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

            clip.audio.export(output_path, format=format)
            logger.info(f"成功导出 ID={clip_id} 到: {output_path}")
            return True
        except Exception as e:
            logger.error(f"导出失败: {e}")
            return False

    def get_summary(self) -> dict:
        """
        获取加载摘要信息

        Returns:
            dict: 包含统计信息的字典
        """
        if not self._loaded:
            return {"loaded": False, "message": "尚未加载音频"}

        anchor_count = sum(1 for c in self.clips if c.clip_type == "ANCHOR")
        floating_count = sum(1 for c in self.clips if c.clip_type == "FLOATING")
        total_duration = self.get_total_duration()

        return {
            "loaded": True,
            "total_clips": len(self.clips),
            "anchor_clips": anchor_count,
            "floating_clips": floating_count,
            "total_duration": round(total_duration, 2),
            "config_path": self.config_path,
            "tts_folder": self.tts_folder,
            "output_folder": self.output_folder,
        }

    def print_summary(self) -> None:
        """打印加载摘要信息"""
        summary = self.get_summary()

        if not summary.get("loaded"):
            print(summary.get("message"))
            return

        print("\n" + "=" * 60)
        print("TTS 加载摘要")
        print("=" * 60)
        print(f"总片段数: {summary['total_clips']}")
        print(f"  - 锚点 (ANCHOR): {summary['anchor_clips']}")
        print(f"  - 浮动块 (FLOATING): {summary['floating_clips']}")
        print(f"总时长: {summary['total_duration']:.2f} 秒")
        print(f"配置文件: {summary['config_path']}")
        print(f"TTS 文件夹: {summary['tts_folder']}")
        print(f"输出文件夹: {summary['output_folder']}")
        print("=" * 60 + "\n")


def main():
    """示例用法"""
    import argparse

    parser = argparse.ArgumentParser(description="TTS 音频加载工具")
    parser.add_argument("config", help="配置文件路径 (.json 或 .xlsx)")
    parser.add_argument("-t", "--tts-folder", required=True, help="TTS 音频文件夹路径")
    parser.add_argument(
        "-o", "--output-folder", default="output", help="输出文件夹路径（默认: output）"
    )
    parser.add_argument("-e", "--export", action="store_true", help="导出所有音频片段")
    parser.add_argument("-f", "--format", default="wav", help="导出格式（默认: wav）")

    args = parser.parse_args()

    try:
        # 创建加载器
        loader = TTSLoader(
            config_path=args.config,
            tts_folder=args.tts_folder,
            output_folder=args.output_folder,
        )

        # 加载 TTS 音频
        success = loader.load_tts()

        if not success:
            logger.error("加载失败")
            sys.exit(1)

        # 打印摘要
        loader.print_summary()

        # 导出音频（如果指定）
        if args.export:
            loader.export_clips(format=args.format)

    except Exception as e:
        logger.error(f"发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
