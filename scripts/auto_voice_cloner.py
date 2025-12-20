#!/usr/bin/env python3
"""
AutoVoiceCloner - 自动化声音克隆工具类

封装 IndexTTS2VoiceCloner 功能，提供单条和批量音频克隆任务。
支持通过JSON配置文件进行批量克隆，或直接传参进行单条克隆。

作者: 高级Python工程师
日期: 2025-12-20
"""

import os
import json
import re
import logging
from typing import Optional, List, Dict
from pathlib import Path
import argparse
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 导入IndexTTS2VoiceCloner
try:
    from scripts.index_tts2_voice_cloner import (
        IndexTTS2VoiceCloner,
        VoiceCloneParams,
        CloneResult,
    )
except ImportError:
    # 如果从scripts导入失败，尝试直接导入
    from index_tts2_voice_cloner import (
        IndexTTS2VoiceCloner,
        VoiceCloneParams,
        CloneResult,
    )

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AutoVoiceCloner:
    """
    自动化声音克隆器

    该类封装了 IndexTTS2VoiceCloner 的功能，提供两种工作模式：
    1. 批量克隆模式：从JSON配置文件读取任务列表，批量生成音频
    2. 单条克隆模式：直接传入参数，生成单个音频

    使用示例：
        >>> # 批量模式
        >>> cloner = AutoVoiceCloner(output_dir="outputs")
        >>> cloner.run_cloning(
        ...     input_audio="speaker.wav",
        ...     batch_json_path="config.json",
        ...     emo_audio_folder="emotions/"
        ... )
        >>>
        >>> # 单条模式
        >>> cloner.run_cloning(
        ...     input_audio="speaker.wav",
        ...     emo_audio="happy.wav",
        ...     emo_text="你好世界"
        ... )
    """

    def __init__(
        self,
        output_dir: str = "outputs",
        cfg_path: Optional[str] = None,
        model_dir: Optional[str] = None,
    ):
        """
        初始化AutoVoiceCloner

        Args:
            output_dir (str): 输出目录，默认为 "outputs"
            cfg_path (Optional[str]): TTS模型配置文件路径
            model_dir (Optional[str]): TTS模型目录路径
        """
        # 创建输出目录
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"输出目录: {self.output_dir}")

        # 初始化底层克隆器
        logger.info("正在初始化 IndexTTS2VoiceCloner...")
        self.cloner = IndexTTS2VoiceCloner(
            cfg_path=cfg_path, model_dir=model_dir, auto_create_output_dir=True
        )
        logger.info("✅ AutoVoiceCloner 初始化完成")

    def run_cloning(
        self,
        input_audio: str,
        batch_json_path: Optional[str] = None,
        emo_audio_folder: Optional[str] = None,
        emo_audio: Optional[str] = None,
        emo_text: Optional[str] = None,
    ) -> Dict:
        """
        执行声音克隆任务（支持单条和批量两种模式）

        **模式判断**：根据 batch_json_path 是否为空自动选择模式

        **批量克隆模式** (batch_json_path 不为空)：
        - 必需参数：input_audio, batch_json_path, emo_audio_folder
        - 从JSON文件读取任务列表，批量生成音频
        - 输出文件名格式：{sort}_{text}.wav

        **单条克隆模式** (batch_json_path 为空)：
        - 必需参数：input_audio, emo_audio, emo_text
        - 直接生成单个音频文件
        - 输出文件名格式：single_{text}.wav

        Args:
            input_audio (str): 目标音色参考音频路径（spk_audio_prompt）
            batch_json_path (Optional[str]): 批量任务的JSON配置文件路径
            emo_audio_folder (Optional[str]): 批量任务中，情感音频文件夹路径
            emo_audio (Optional[str]): 单条模式下的情感参考音频
            emo_text (Optional[str]): 单条模式下的目标文本

        Returns:
            Dict: 执行结果统计
                - mode: 执行模式 ("batch" 或 "single")
                - total: 总任务数
                - success: 成功数量
                - failed: 失败数量
                - results: 详细结果列表
        """
        # 验证input_audio
        if not input_audio:
            raise ValueError("input_audio 参数是必需的")
        if not os.path.exists(input_audio):
            raise FileNotFoundError(f"音色参考音频不存在: {input_audio}")

        # 根据 batch_json_path 判断模式
        if batch_json_path:
            # 批量克隆模式
            return self._run_batch_mode(
                input_audio=input_audio,
                batch_json_path=batch_json_path,
                emo_audio_folder=emo_audio_folder,
            )
        else:
            # 单条克隆模式
            return self._run_single_mode(
                input_audio=input_audio, emo_audio=emo_audio, emo_text=emo_text
            )

    def _run_batch_mode(
        self,
        input_audio: str,
        batch_json_path: str,
        emo_audio_folder: Optional[str] = None,
    ) -> Dict:
        """
        执行批量克隆模式

        Args:
            input_audio (str): 音色参考音频
            batch_json_path (str): JSON配置文件路径
            emo_audio_folder (Optional[str]): 情感音频文件夹路径

        Returns:
            Dict: 执行结果
        """
        logger.info("=" * 70)
        logger.info("[批量克隆模式] 开始执行")
        logger.info("=" * 70)

        # 验证参数
        if not os.path.exists(batch_json_path):
            raise FileNotFoundError(f"JSON配置文件不存在: {batch_json_path}")

        if emo_audio_folder and not os.path.exists(emo_audio_folder):
            raise FileNotFoundError(f"情感音频文件夹不存在: {emo_audio_folder}")

        # 读取JSON配置
        logger.info(f"读取配置文件: {batch_json_path}")
        with open(batch_json_path, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        if not isinstance(tasks, list):
            raise ValueError("JSON文件内容必须是数组")

        # 按 sort 字段排序（正序）
        tasks_sorted = sorted(tasks, key=lambda x: int(x.get("sort", x.get("id", 0))))
        total_tasks = len(tasks_sorted)

        logger.info(f"共加载 {total_tasks} 个任务")
        logger.info(f"音色参考: {input_audio}")
        if emo_audio_folder:
            logger.info(f"情感音频文件夹: {emo_audio_folder}")
        logger.info("=" * 70)

        # 执行批量克隆
        results = []
        success_count = 0
        failed_count = 0

        for idx, task in enumerate(tasks_sorted, 1):
            try:
                # 提取任务参数
                sort_num = task.get("sort", task.get("id", idx))
                text = task.get("text", "")
                emo_filename = task.get("emo_audio", task.get("filename", ""))

                if not text:
                    logger.warning(
                        f"[{idx}/{total_tasks}] 任务 {sort_num} 缺少文本，跳过"
                    )
                    failed_count += 1
                    results.append(
                        {"sort": sort_num, "success": False, "error": "缺少文本内容"}
                    )
                    continue

                # 构建情感音频路径
                if emo_audio_folder and emo_filename:
                    emo_audio_path = os.path.join(emo_audio_folder, emo_filename)
                else:
                    emo_audio_path = emo_filename if emo_filename else None

                # 验证情感音频是否存在
                if emo_audio_path and not os.path.exists(emo_audio_path):
                    logger.warning(
                        f"[{idx}/{total_tasks}] 情感音频不存在: {emo_audio_path}，跳过"
                    )
                    failed_count += 1
                    results.append(
                        {
                            "sort": sort_num,
                            "success": False,
                            "error": f"情感音频不存在: {emo_audio_path}",
                        }
                    )
                    continue

                # 清洗文本，移除非法字符
                clean_text = self._sanitize_filename(text)

                # 构建输出文件名：{sort}_{text}.wav
                output_filename = f"{sort_num}_{clean_text}.wav"
                output_path = str(self.output_dir / output_filename)

                # 显示进度
                logger.info(f"[批量模式] 正在处理 {idx}/{total_tasks}...")
                logger.info(f"  序号: {sort_num}")
                logger.info(
                    f"  文本: {text[:40]}..." if len(text) > 40 else f"  文本: {text}"
                )
                logger.info(f"  情感音频: {emo_filename}")
                logger.info(f"  输出文件: {output_filename}")

                # 执行克隆
                result = self.cloner.clone_with_emotion_audio(
                    text=text,
                    spk_audio_prompt=input_audio,
                    emo_audio_prompt=emo_audio_path,
                    output_path=output_path,
                    verbose=False,  # 关闭详细日志以减少输出
                )

                if result.success:
                    success_count += 1
                    logger.info(f"  ✅ 成功 ({result.duration_ms}ms)")
                    results.append(
                        {
                            "sort": sort_num,
                            "text": text,
                            "output_path": output_path,
                            "success": True,
                            "duration_ms": result.duration_ms,
                        }
                    )
                else:
                    failed_count += 1
                    logger.error(f"  ❌ 失败: {result.error_message}")
                    results.append(
                        {
                            "sort": sort_num,
                            "text": text,
                            "success": False,
                            "error": result.error_message,
                        }
                    )

            except Exception as e:
                failed_count += 1
                logger.error(f"[{idx}/{total_tasks}] 处理任务时出错: {str(e)}")
                results.append(
                    {"sort": task.get("sort", idx), "success": False, "error": str(e)}
                )

        # 输出统计信息
        logger.info("=" * 70)
        logger.info("[批量克隆模式] 执行完成")
        logger.info(f"总任务数: {total_tasks}")
        logger.info(f"成功: {success_count}")
        logger.info(f"失败: {failed_count}")
        logger.info(f"成功率: {success_count / total_tasks * 100:.1f}%")
        logger.info("=" * 70)

        return {
            "mode": "batch",
            "total": total_tasks,
            "success": success_count,
            "failed": failed_count,
            "results": results,
        }

    def _run_single_mode(
        self,
        input_audio: str,
        emo_audio: Optional[str] = None,
        emo_text: Optional[str] = None,
    ) -> Dict:
        """
        执行单条克隆模式

        Args:
            input_audio (str): 音色参考音频
            emo_audio (Optional[str]): 情感参考音频
            emo_text (Optional[str]): 目标文本

        Returns:
            Dict: 执行结果
        """
        logger.info("=" * 70)
        logger.info("[单条克隆模式] 开始执行")
        logger.info("=" * 70)

        # 验证参数
        if not emo_audio:
            raise ValueError("单条模式下，emo_audio 参数是必需的")
        if not emo_text:
            raise ValueError("单条模式下，emo_text 参数是必需的")

        if not os.path.exists(emo_audio):
            raise FileNotFoundError(f"情感参考音频不存在: {emo_audio}")

        # 清洗文本
        clean_text = self._sanitize_filename(emo_text)

        # 构建输出文件名：single_{text}.wav
        output_filename = f"single_{clean_text}.wav"
        output_path = str(self.output_dir / output_filename)

        logger.info(f"音色参考: {input_audio}")
        logger.info(f"情感参考: {emo_audio}")
        logger.info(f"目标文本: {emo_text}")
        logger.info(f"输出文件: {output_filename}")
        logger.info("=" * 70)

        # 执行克隆
        result = self.cloner.clone_with_emotion_audio(
            text=emo_text,
            spk_audio_prompt=input_audio,
            emo_audio_prompt=emo_audio,
            output_path=output_path,
            verbose=True,
        )

        # 输出结果
        if result.success:
            logger.info("=" * 70)
            logger.info("[单条克隆模式] ✅ 执行成功")
            logger.info(f"输出文件: {output_path}")
            logger.info(f"耗时: {result.duration_ms}ms")
            logger.info("=" * 70)
        else:
            logger.error("=" * 70)
            logger.error("[单条克隆模式] ❌ 执行失败")
            logger.error(f"错误信息: {result.error_message}")
            logger.error("=" * 70)

        return {
            "mode": "single",
            "total": 1,
            "success": 1 if result.success else 0,
            "failed": 0 if result.success else 1,
            "results": [
                {
                    "text": emo_text,
                    "output_path": output_path if result.success else None,
                    "success": result.success,
                    "error": result.error_message if not result.success else None,
                    "duration_ms": result.duration_ms,
                }
            ],
        }

    @staticmethod
    def _sanitize_filename(text: str, max_length: int = 50) -> str:
        """
        清洗文本，移除文件名中的非法字符

        Args:
            text (str): 原始文本
            max_length (int): 最大长度，默认50个字符

        Returns:
            str: 清洗后的文本
        """
        # 移除或替换非法字符
        # Windows 文件名非法字符: < > : " / \ | ? *
        illegal_chars = r'[<>:"/\\|?*]'
        clean = re.sub(illegal_chars, "_", text)

        # 移除前后空格
        clean = clean.strip()

        # 移除连续的下划线
        clean = re.sub(r"_{2,}", "_", clean)

        # 限制长度
        if len(clean) > max_length:
            clean = clean[:max_length]

        # 移除 llm_ 开头的时间戳标记（如果有）
        clean = re.sub(r"^llm_\d+_[\d.]+s_", "", clean)

        # 如果清洗后为空，使用默认名称
        if not clean:
            clean = "unnamed"

        return clean


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    # 1. 定义命令行参数解析器
    parser = argparse.ArgumentParser(description="AutoVoiceCloner - 自动音频克隆工具")

    # === 公共参数 ===
    parser.add_argument(
        "-i",
        "--input_audio",
        type=str,
        required=True,
        help="【必须】说话人音色参考音频路径 (Input Speaker)",
    )

    # [修正点] 删除了 --model_path 和 --device 参数定义

    # === 批量模式参数 ===
    parser.add_argument(
        "-j",
        "--json_path",
        type=str,
        help="【批量】JSON 配置文件路径 (存在即开启批量模式)",
    )
    parser.add_argument(
        "-f", "--audio_folder", type=str, help="【批量】参考音频所在的文件夹路径"
    )

    # === 单条模式参数 ===
    parser.add_argument("-a", "--emo_audio", type=str, help="【单条】情感参考音频路径")
    parser.add_argument("-t", "--emo_text", type=str, help="【单条】目标生成文本")

    args = parser.parse_args()

    # 2. 参数校验逻辑
    if args.json_path:
        # --- 进入批量模式校验 ---
        if not args.audio_folder:
            print("❌ 错误: 批量模式下，必须提供 -f / --audio_folder 参数")
            sys.exit(1)
        mode_msg = f"批量模式 (配置文件: {args.json_path})"
    else:
        # --- 进入单条模式校验 ---
        if not args.emo_audio or not args.emo_text:
            print("❌ 错误: 单条模式下，必须提供 -a (音频) 和 -t (文本) 参数")
            sys.exit(1)
        mode_msg = "单条模式"

    print("=" * 50)
    print(f"🚀 启动 AutoVoiceCloner - {mode_msg}")
    print(f"🎤 输入音色: {args.input_audio}")
    print("=" * 50)

    try:
        # 3. 初始化模型
        # [修正点] 不再传递 model_path 和 device，直接空参初始化
        # 这样它就会使用类内部默认封装好的配置
        cloner = AutoVoiceCloner()

        # 4. 执行克隆
        cloner.run_cloning(
            input_audio=args.input_audio,
            batch_json_path=args.json_path,  # 如果没传，这里是 None
            emo_audio_folder=args.audio_folder,  # 如果没传，这里是 None
            emo_audio=args.emo_audio,  # 如果没传，这里是 None
            emo_text=args.emo_text,  # 如果没传，这里是 None
        )

    except Exception as e:
        print(f"\n❌ 程序执行出错: {str(e)}")
        # 打印详细错误堆栈，方便排查其他问题
        import traceback

        traceback.print_exc()
        sys.exit(1)

# if __name__ == "__main__":
#     print("\n" + "=" * 70)
#     print("AutoVoiceCloner 使用示例")
#     print("=" * 70)

#     # 创建克隆器实例
#     try:
#         cloner = AutoVoiceCloner(output_dir="outputs/auto_cloner")
#     except Exception as e:
#         print(f"❌ 初始化失败: {e}")
#         print("提示：请确保已正确安装 indextts 包")
#         exit(1)

#     # ========================================================================
#     # 示例1：批量克隆模式
#     # ========================================================================
#     print("\n" + "-" * 70)
#     print("示例1：批量克隆模式")
#     print("-" * 70)
#     print("""
# 使用场景：
# - 有一个JSON配置文件，包含多个待生成的文本
# - 所有文本使用同一个说话人音色
# - 每个文本对应不同的情感参考音频

# 调用方式：
#     result = cloner.run_cloning(
#         input_audio="speaker.wav",
#         batch_json_path="db/sherlock_holmes_narrator_01.json",
#         emo_audio_folder="role_audio/福尔摩斯第一集原人声切片/旁白"
#     )

# 执行流程：
# 1. 读取JSON文件
# 2. 按 sort 字段正序排序
# 3. 遍历每个任务：
#    - text = JSON中的text字段
#    - emo_audio = emo_audio_folder + JSON中的emo_audio字段
#    - spk_audio = input_audio
# 4. 输出文件命名：{sort}_{text}.wav
#    例如：1_今年伦敦的春天似乎比往年来得早些.wav
#     """)

#     # 实际执行（注释掉，避免实际运行）
#     # result = cloner.run_cloning(
#     #     input_audio="speaker.wav",
#     #     batch_json_path="db/sherlock_holmes_narrator_01.json",
#     #     emo_audio_folder="role_audio/福尔摩斯第一集原人声切片/旁白"
#     # )
#     # print(f"批量克隆结果: 成功 {result['success']}/{result['total']}")

#     # ========================================================================
#     # 示例2：单条克隆模式
#     # ========================================================================
#     print("\n" + "-" * 70)
#     print("示例2：单条克隆模式")
#     print("-" * 70)
#     print("""
# 使用场景：
# - 快速生成单个音频
# - 不需要JSON配置文件

# 调用方式：
#     result = cloner.run_cloning(
#         input_audio="speaker.wav",
#         emo_audio="emotion.wav",
#         emo_text="你好，今天天气真好！"
#     )

# 执行流程：
# 1. 直接使用传入的参数
# 2. 生成单个音频文件
# 3. 输出文件命名：single_{text}.wav
#    例如：single_你好今天天气真好.wav
#     """)

#     # 实际执行（注释掉，避免实际运行）
#     # result = cloner.run_cloning(
#     #     input_audio="speaker.wav",
#     #     emo_audio="emotion.wav",
#     #     emo_text="你好，今天天气真好！"
#     # )
#     # print(f"单条克隆结果: {'成功' if result['success'] else '失败'}")

#     # ========================================================================
#     # 完整示例（实际可运行）
#     # ========================================================================
#     print("\n" + "-" * 70)
#     print("完整示例代码")
#     print("-" * 70)
#     print("""
# from scripts.auto_voice_cloner import AutoVoiceCloner

# # 创建克隆器
# cloner = AutoVoiceCloner(output_dir="outputs/my_audio")

# # 批量克隆
# batch_result = cloner.run_cloning(
#     input_audio="/path/to/speaker_voice.wav",
#     batch_json_path="db/sherlock_holmes_narrator_01.json",
#     emo_audio_folder="/path/to/emotion_audios/"
# )

# print(f"批量克隆: {batch_result['success']}/{batch_result['total']} 成功")

# # 单条克隆
# single_result = cloner.run_cloning(
#     input_audio="/path/to/speaker_voice.wav",
#     emo_audio="/path/to/happy_emotion.wav",
#     emo_text="今天天气真好！"
# )

# print(f"单条克隆: {'✅成功' if single_result['success'] else '❌失败'}")
#     """)

#     print("\n" + "=" * 70)
#     print("示例展示完成")
#     print("=" * 70)
#     print("\n提示：修改上述示例中的路径后即可实际运行")
