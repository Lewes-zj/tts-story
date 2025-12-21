"""
Index-TTS2 声音克隆器 (Voice Cloner)

提供统一的接口来调用 Index-TTS2 模型进行声音克隆，支持：
1. 基于情感参考音频的声音克隆
2. 基于情感向量的声音克隆
3. 批量音频生成
4. 灵活的参数配置

作为公共类，可以被项目中的其他模块复用。
"""

import os
import time
import logging
from typing import Optional, List, Dict, Union
from dataclasses import dataclass, field

# 导入TTS工具函数
from scripts.tts_utils import initialize_tts_model, TTS_AVAILABLE, IndexTTS2


# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class VoiceCloneParams:
    """
    声音克隆参数配置类

    Attributes:
        text (str): 要转换为语音的文本内容
        spk_audio_prompt (str): 说话人音频提示路径，用于克隆音色
        output_path (str): 输出音频文件路径
        emo_audio_prompt (Optional[str]): 情感参考音频路径，用于情感迁移
        emo_alpha (Optional[float]): 情感混合系数，范围 [0.0, 1.0]，默认 0.65
        emo_vector (Optional[List[float]]): 情感向量，8维向量
        temperature (float): 采样温度，控制随机性，默认 0.3
        top_p (float): Top-P (nucleus) 采样参数，默认 0.8
        verbose (bool): 是否输出详细日志，默认 True
    """

    text: str
    spk_audio_prompt: str
    output_path: str
    emo_audio_prompt: Optional[str] = None
    emo_alpha: float = 0.65
    emo_vector: Optional[List[float]] = None
    temperature: float = 0.3
    top_p: float = 0.8
    verbose: bool = True

    def __post_init__(self):
        """参数验证"""
        if not self.text:
            raise ValueError("text 参数不能为空")
        if not self.spk_audio_prompt:
            raise ValueError("spk_audio_prompt 参数不能为空")
        if not self.output_path:
            raise ValueError("output_path 参数不能为空")
        if not (0.0 <= self.emo_alpha <= 1.0):
            raise ValueError("emo_alpha 必须在 [0.0, 1.0] 范围内")
        if self.emo_vector is not None and len(self.emo_vector) != 8:
            raise ValueError("emo_vector 必须是长度为 8 的向量")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("temperature 必须在 [0.0, 2.0] 范围内")
        if not (0.0 <= self.top_p <= 1.0):
            raise ValueError("top_p 必须在 [0.0, 1.0] 范围内")


@dataclass
class CloneResult:
    """
    声音克隆结果类

    Attributes:
        success (bool): 是否成功
        output_path (Optional[str]): 输出文件路径
        error_message (Optional[str]): 错误信息
        duration_ms (int): 生成耗时（毫秒）
    """

    success: bool
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: int = 0


class IndexTTS2VoiceCloner:
    """
    Index-TTS2 声音克隆器

    该类提供了统一的接口来调用 Index-TTS2 模型进行声音克隆。
    支持两种克隆模式：
    1. 基于情感参考音频 (emo_audio_prompt)
    2. 基于情感向量 (emo_vector + emo_alpha)

    使用示例：
        >>> cloner = IndexTTS2VoiceCloner()
        >>>
        >>> # 方式1：使用情感参考音频
        >>> result = cloner.clone_with_emotion_audio(
        ...     text="你好，世界！",
        ...     spk_audio_prompt="path/to/speaker.wav",
        ...     emo_audio_prompt="path/to/emotion.wav",
        ...     output_path="output.wav"
        ... )
        >>>
        >>> # 方式2：使用情感向量
        >>> result = cloner.clone_with_emotion_vector(
        ...     text="你好，世界！",
        ...     spk_audio_prompt="path/to/speaker.wav",
        ...     emo_vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        ...     emo_alpha=0.65,
        ...     output_path="output.wav"
        ... )
        >>>
        >>> # 方式3：灵活参数配置
        >>> params = VoiceCloneParams(
        ...     text="你好，世界！",
        ...     spk_audio_prompt="path/to/speaker.wav",
        ...     emo_audio_prompt="path/to/emotion.wav",
        ...     output_path="output.wav"
        ... )
        >>> result = cloner.clone(params)
    """

    def __init__(
        self,
        cfg_path: Optional[str] = None,
        model_dir: Optional[str] = None,
        auto_create_output_dir: bool = True,
    ):
        """
        初始化声音克隆器

        Args:
            cfg_path (Optional[str]): TTS模型配置文件路径
            model_dir (Optional[str]): TTS模型目录路径
            auto_create_output_dir (bool): 是否自动创建输出目录，默认 True

        Raises:
            RuntimeError: 当TTS功能不可用或模型初始化失败时抛出
        """
        if not TTS_AVAILABLE:
            raise RuntimeError(
                "TTS 功能不可用，请确保已正确安装 indextts 包\n"
                "安装方法：pip install indextts"
            )

        logger.info("正在初始化 Index-TTS2 声音克隆器...")

        # 初始化TTS模型
        self.tts_model: Optional[IndexTTS2] = initialize_tts_model(
            cfg_path=cfg_path, model_dir=model_dir
        )

        if self.tts_model is None:
            raise RuntimeError("Index-TTS2 模型初始化失败")

        self.auto_create_output_dir = auto_create_output_dir
        logger.info("✅ Index-TTS2 声音克隆器初始化成功")

    def clone(self, params: VoiceCloneParams) -> CloneResult:
        """
        执行声音克隆（通用方法）

        根据提供的参数自动选择克隆模式：
        - 如果提供了 emo_audio_prompt，使用情感参考音频模式
        - 如果提供了 emo_vector，使用情感向量模式
        - 两者都提供时，优先使用情感参考音频模式

        Args:
            params (VoiceCloneParams): 声音克隆参数配置

        Returns:
            CloneResult: 克隆结果
        """
        start_time = time.time()

        try:
            # 验证说话人音频文件是否存在
            if not os.path.exists(params.spk_audio_prompt):
                raise FileNotFoundError(
                    f"说话人音频文件不存在: {params.spk_audio_prompt}"
                )

            # 如果提供了情感参考音频，验证其是否存在
            if params.emo_audio_prompt and not os.path.exists(params.emo_audio_prompt):
                raise FileNotFoundError(
                    f"情感参考音频文件不存在: {params.emo_audio_prompt}"
                )

            # 自动创建输出目录
            if self.auto_create_output_dir:
                output_dir = os.path.dirname(params.output_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                    logger.info(f"已创建输出目录: {output_dir}")

            # 记录调用参数
            if params.verbose:
                logger.info(f"开始声音克隆: text='{params.text[:50]}...'")
                logger.info(f"  说话人音频: {params.spk_audio_prompt}")
                if params.emo_audio_prompt:
                    logger.info(f"  情感参考音频: {params.emo_audio_prompt}")
                if params.emo_vector:
                    logger.info(f"  情感向量: {params.emo_vector}")
                    logger.info(f"  情感混合系数: {params.emo_alpha}")
                logger.info(f"  输出路径: {params.output_path}")

            # 调用 Index-TTS2 模型进行推理
            self.tts_model.infer(
                spk_audio_prompt=params.spk_audio_prompt,
                text=params.text,
                emo_audio_prompt=params.emo_audio_prompt,
                temperature=params.temperature,
                top_p=params.top_p,
                output_path=params.output_path,
                emo_alpha=params.emo_alpha,
                emo_vector=params.emo_vector,
                verbose=params.verbose,
            )

            # 验证输出文件是否生成
            if not os.path.exists(params.output_path):
                raise RuntimeError(
                    f"模型推理完成，但未生成输出文件: {params.output_path}"
                )

            # 验证文件大小（防止生成空文件）
            file_size = os.path.getsize(params.output_path)
            if file_size < 100:  # 小于100字节认为是无效文件
                raise RuntimeError(f"生成的音频文件过小 ({file_size} bytes)，可能无效")

            duration_ms = int((time.time() - start_time) * 1000)

            if params.verbose:
                logger.info(f"✅ 声音克隆成功，耗时: {duration_ms}ms")
                logger.info(f"   输出文件: {params.output_path} ({file_size} bytes)")

            return CloneResult(
                success=True, output_path=params.output_path, duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"声音克隆失败: {str(e)}"
            logger.error(error_msg)

            return CloneResult(
                success=False, error_message=error_msg, duration_ms=duration_ms
            )

    def clone_with_emotion_audio(
        self,
        text: str,
        spk_audio_prompt: str,
        emo_audio_prompt: str,
        output_path: str,
        verbose: bool = True,
    ) -> CloneResult:
        """
        使用情感参考音频进行声音克隆

        这是最常用的克隆方式，通过提供一个情感参考音频，
        模型会克隆说话人的音色，同时迁移参考音频中的情感特征。

        Args:
            text (str): 要转换为语音的文本
            spk_audio_prompt (str): 说话人音频路径（音色来源）
            emo_audio_prompt (str): 情感参考音频路径（情感来源）
            output_path (str): 输出音频路径
            verbose (bool): 是否输出详细日志

        Returns:
            CloneResult: 克隆结果

        示例：
            >>> cloner = IndexTTS2VoiceCloner()
            >>> result = cloner.clone_with_emotion_audio(
            ...     text="今天天气真好！",
            ...     spk_audio_prompt="speaker_samples/alice.wav",
            ...     emo_audio_prompt="emotion_samples/happy.wav",
            ...     output_path="outputs/result.wav"
            ... )
            >>> if result.success:
            ...     print(f"成功！文件保存在: {result.output_path}")
        """
        params = VoiceCloneParams(
            text=text,
            spk_audio_prompt=spk_audio_prompt,
            emo_audio_prompt=emo_audio_prompt,
            top_p=0.8,
            temperature=0.3,
            output_path=output_path,
            verbose=verbose,
        )
        return self.clone(params)

    def clone_with_emotion_vector(
        self,
        text: str,
        spk_audio_prompt: str,
        emo_vector: List[float],
        output_path: str,
        emo_alpha: float = 0.65,
        verbose: bool = True,
    ) -> CloneResult:
        """
        使用情感向量进行声音克隆

        通过直接指定8维情感向量来控制生成音频的情感特征。
        这种方式更加精确，适合需要细粒度控制情感的场景。

        Args:
            text (str): 要转换为语音的文本
            spk_audio_prompt (str): 说话人音频路径（音色来源）
            emo_vector (List[float]): 情感向量，8维浮点数列表
            output_path (str): 输出音频路径
            emo_alpha (float): 情感混合系数 [0.0, 1.0]，默认 0.65
            verbose (bool): 是否输出详细日志

        Returns:
            CloneResult: 克隆结果

        示例：
            >>> cloner = IndexTTS2VoiceCloner()
            >>> result = cloner.clone_with_emotion_vector(
            ...     text="我很开心！",
            ...     spk_audio_prompt="speaker_samples/alice.wav",
            ...     emo_vector=[0.8, 0.2, 0.1, 0.3, 0.5, 0.4, 0.6, 0.7],
            ...     emo_alpha=0.7,
            ...     output_path="outputs/result.wav"
            ... )
        """
        params = VoiceCloneParams(
            text=text,
            spk_audio_prompt=spk_audio_prompt,
            emo_vector=emo_vector,
            emo_alpha=emo_alpha,
            output_path=output_path,
            verbose=verbose,
        )
        return self.clone(params)

    def clone_batch(self, params_list: List[VoiceCloneParams]) -> List[CloneResult]:
        """
        批量声音克隆

        依次处理多个克隆任务，返回所有结果。
        即使某个任务失败，也会继续处理后续任务。

        Args:
            params_list (List[VoiceCloneParams]): 参数列表

        Returns:
            List[CloneResult]: 结果列表

        示例：
            >>> cloner = IndexTTS2VoiceCloner()
            >>> params_list = [
            ...     VoiceCloneParams(
            ...         text="第一句话",
            ...         spk_audio_prompt="speaker.wav",
            ...         emo_audio_prompt="happy.wav",
            ...         output_path="output1.wav"
            ...     ),
            ...     VoiceCloneParams(
            ...         text="第二句话",
            ...         spk_audio_prompt="speaker.wav",
            ...         emo_audio_prompt="sad.wav",
            ...         output_path="output2.wav"
            ...     ),
            ... ]
            >>> results = cloner.clone_batch(params_list)
            >>> success_count = sum(1 for r in results if r.success)
            >>> print(f"成功: {success_count}/{len(results)}")
        """
        logger.info(f"开始批量声音克隆，共 {len(params_list)} 个任务")

        results = []
        success_count = 0

        for i, params in enumerate(params_list, 1):
            logger.info(f"处理第 {i}/{len(params_list)} 个任务")
            result = self.clone(params)
            results.append(result)

            if result.success:
                success_count += 1

        logger.info(f"批量克隆完成：成功 {success_count}/{len(params_list)} 个任务")

        return results

    def clone_with_auto_output_path(
        self,
        text: str,
        spk_audio_prompt: str,
        emo_audio_prompt: Optional[str] = None,
        emo_vector: Optional[List[float]] = None,
        emo_alpha: float = 0.65,
        output_dir: str = "outputs",
        output_prefix: str = "clone",
        verbose: bool = True,
    ) -> CloneResult:
        """
        自动生成输出路径的声音克隆

        输出文件名格式: {output_prefix}_{timestamp}.wav

        Args:
            text (str): 要转换为语音的文本
            spk_audio_prompt (str): 说话人音频路径
            emo_audio_prompt (Optional[str]): 情感参考音频路径
            emo_vector (Optional[List[float]]): 情感向量
            emo_alpha (float): 情感混合系数
            output_dir (str): 输出目录，默认 "outputs"
            output_prefix (str): 输出文件名前缀，默认 "clone"
            verbose (bool): 是否输出详细日志

        Returns:
            CloneResult: 克隆结果

        示例：
            >>> cloner = IndexTTS2VoiceCloner()
            >>> result = cloner.clone_with_auto_output_path(
            ...     text="自动命名测试",
            ...     spk_audio_prompt="speaker.wav",
            ...     emo_audio_prompt="happy.wav",
            ...     output_dir="my_outputs",
            ...     output_prefix="test"
            ... )
            >>> # 输出文件: my_outputs/test_1703123456789.wav
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 生成带时间戳的文件名
        timestamp = int(time.time() * 1000)
        output_filename = f"{output_prefix}_{timestamp}.wav"
        output_path = os.path.join(output_dir, output_filename)

        params = VoiceCloneParams(
            text=text,
            spk_audio_prompt=spk_audio_prompt,
            emo_audio_prompt=emo_audio_prompt,
            emo_vector=emo_vector,
            emo_alpha=emo_alpha,
            output_path=output_path,
            verbose=verbose,
        )

        return self.clone(params)


# ============================================================================
# 便捷函数（供快速调用）
# ============================================================================


def quick_clone_with_emotion(
    text: str, speaker_audio: str, emotion_audio: str, output_path: str, **kwargs
) -> bool:
    """
    快速克隆（使用情感参考音频）

    便捷函数，简化常用场景的调用。

    Args:
        text (str): 文本内容
        speaker_audio (str): 说话人音频路径
        emotion_audio (str): 情感参考音频路径
        output_path (str): 输出路径
        **kwargs: 其他可选参数

    Returns:
        bool: 是否成功

    示例：
        >>> from scripts.index_tts2_voice_cloner import quick_clone_with_emotion
        >>> success = quick_clone_with_emotion(
        ...     text="快速测试",
        ...     speaker_audio="speaker.wav",
        ...     emotion_audio="happy.wav",
        ...     output_path="output.wav"
        ... )
    """
    try:
        cloner = IndexTTS2VoiceCloner()
        result = cloner.clone_with_emotion_audio(
            text=text,
            spk_audio_prompt=speaker_audio,
            emo_audio_prompt=emotion_audio,
            output_path=output_path,
            **kwargs,
        )
        return result.success
    except Exception as e:
        logger.error(f"快速克隆失败: {e}")
        return False


def quick_clone_with_vector(
    text: str,
    speaker_audio: str,
    emotion_vector: List[float],
    output_path: str,
    emo_alpha: float = 0.65,
    **kwargs,
) -> bool:
    """
    快速克隆（使用情感向量）

    便捷函数，简化常用场景的调用。

    Args:
        text (str): 文本内容
        speaker_audio (str): 说话人音频路径
        emotion_vector (List[float]): 情感向量
        output_path (str): 输出路径
        emo_alpha (float): 情感混合系数
        **kwargs: 其他可选参数

    Returns:
        bool: 是否成功

    示例：
        >>> from scripts.index_tts2_voice_cloner import quick_clone_with_vector
        >>> success = quick_clone_with_vector(
        ...     text="快速测试",
        ...     speaker_audio="speaker.wav",
        ...     emotion_vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        ...     output_path="output.wav"
        ... )
    """
    try:
        cloner = IndexTTS2VoiceCloner()
        result = cloner.clone_with_emotion_vector(
            text=text,
            spk_audio_prompt=speaker_audio,
            emo_vector=emotion_vector,
            output_path=output_path,
            emo_alpha=emo_alpha,
            **kwargs,
        )
        return result.success
    except Exception as e:
        logger.error(f"快速克隆失败: {e}")
        return False


# ============================================================================
# 示例用法
# ============================================================================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 示例1：使用情感参考音频
    print("\n" + "=" * 60)
    print("示例1：使用情感参考音频进行声音克隆")
    print("=" * 60)

    try:
        cloner = IndexTTS2VoiceCloner()

        result = cloner.clone_with_emotion_audio(
            text="你好，今天天气真好！",
            spk_audio_prompt="/path/to/speaker.wav",  # 请替换为实际路径
            emo_audio_prompt="/path/to/emotion.wav",  # 请替换为实际路径
            output_path="outputs/example1.wav",
        )

        if result.success:
            print(f"✅ 成功！文件保存在: {result.output_path}")
            print(f"   耗时: {result.duration_ms}ms")
        else:
            print(f"❌ 失败: {result.error_message}")

    except Exception as e:
        print(f"❌ 示例1执行失败: {e}")

    # 示例2：使用情感向量
    print("\n" + "=" * 60)
    print("示例2：使用情感向量进行声音克隆")
    print("=" * 60)

    try:
        cloner = IndexTTS2VoiceCloner()

        result = cloner.clone_with_emotion_vector(
            text="我很开心！",
            spk_audio_prompt="/path/to/speaker.wav",  # 请替换为实际路径
            emo_vector=[0.8, 0.2, 0.1, 0.3, 0.5, 0.4, 0.6, 0.7],
            emo_alpha=0.7,
            output_path="outputs/example2.wav",
        )

        if result.success:
            print(f"✅ 成功！文件保存在: {result.output_path}")
        else:
            print(f"❌ 失败: {result.error_message}")

    except Exception as e:
        print(f"❌ 示例2执行失败: {e}")

    # 示例3：批量克隆
    print("\n" + "=" * 60)
    print("示例3：批量声音克隆")
    print("=" * 60)

    try:
        cloner = IndexTTS2VoiceCloner()

        params_list = [
            VoiceCloneParams(
                text="第一句话",
                spk_audio_prompt="/path/to/speaker.wav",
                emo_audio_prompt="/path/to/happy.wav",
                output_path="outputs/batch1.wav",
            ),
            VoiceCloneParams(
                text="第二句话",
                spk_audio_prompt="/path/to/speaker.wav",
                emo_audio_prompt="/path/to/sad.wav",
                output_path="outputs/batch2.wav",
            ),
        ]

        results = cloner.clone_batch(params_list)

        success_count = sum(1 for r in results if r.success)
        print(f"批量克隆完成：成功 {success_count}/{len(results)} 个")

    except Exception as e:
        print(f"❌ 示例3执行失败: {e}")

    # 示例4：自动生成输出路径
    print("\n" + "=" * 60)
    print("示例4：自动生成输出路径")
    print("=" * 60)

    try:
        cloner = IndexTTS2VoiceCloner()

        result = cloner.clone_with_auto_output_path(
            text="自动命名测试",
            spk_audio_prompt="/path/to/speaker.wav",
            emo_audio_prompt="/path/to/emotion.wav",
            output_dir="outputs",
            output_prefix="auto_test",
        )

        if result.success:
            print(f"✅ 成功！文件自动保存在: {result.output_path}")
        else:
            print(f"❌ 失败: {result.error_message}")

    except Exception as e:
        print(f"❌ 示例4执行失败: {e}")

    print("\n" + "=" * 60)
    print("所有示例执行完成")
    print("=" * 60)
