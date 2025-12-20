"""
Index-TTS2 声音克隆器测试脚本

演示如何使用 IndexTTS2VoiceCloner 类进行声音克隆
"""

import os
import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from scripts.index_tts2_voice_cloner import (
    IndexTTS2VoiceCloner,
    VoiceCloneParams,
    quick_clone_with_emotion,
    quick_clone_with_vector,
)


def test_basic_usage():
    """测试基本用法"""
    print("\n" + "=" * 70)
    print("测试1：基本用法 - 使用情感参考音频")
    print("=" * 70)

    try:
        # 创建克隆器实例
        cloner = IndexTTS2VoiceCloner()

        # 使用情感参考音频进行克隆
        result = cloner.clone_with_emotion_audio(
            text="你好，今天天气真好！我们一起去公园散步吧。",
            spk_audio_prompt="role_audio/guo_08/guo_08_001.wav",  # 音色来源
            emo_audio_prompt="role_audio/guo_08/guo_08_002.wav",  # 情感来源
            output_path="outputs/test_basic.wav",
        )

        if result.success:
            print(f"✅ 成功生成音频")
            print(f"   输出文件: {result.output_path}")
            print(f"   耗时: {result.duration_ms}ms")
        else:
            print(f"❌ 生成失败: {result.error_message}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")


def test_emotion_vector():
    """测试使用情感向量"""
    print("\n" + "=" * 70)
    print("测试2：使用情感向量控制情感")
    print("=" * 70)

    try:
        cloner = IndexTTS2VoiceCloner()

        # 使用情感向量进行克隆
        # 情感向量是8维向量，可以精确控制不同维度的情感特征
        result = cloner.clone_with_emotion_vector(
            text="我真的非常开心，今天是个美好的日子！",
            spk_audio_prompt="role_audio/guo_08/guo_08_001.wav",
            emo_vector=[0.8, 0.2, 0.1, 0.3, 0.5, 0.4, 0.6, 0.7],  # 自定义情感向量
            emo_alpha=0.7,  # 情感混合系数
            output_path="outputs/test_vector.wav",
        )

        if result.success:
            print(f"✅ 成功生成音频")
            print(f"   输出文件: {result.output_path}")
        else:
            print(f"❌ 生成失败: {result.error_message}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")


def test_batch_clone():
    """测试批量克隆"""
    print("\n" + "=" * 70)
    print("测试3：批量声音克隆")
    print("=" * 70)

    try:
        cloner = IndexTTS2VoiceCloner()

        # 准备批量任务参数
        texts = [
            "早上好，欢迎来到新的一天！",
            "下午茶时间到了，休息一下吧。",
            "晚安，祝你有个好梦。",
        ]

        params_list = []
        for i, text in enumerate(texts):
            params = VoiceCloneParams(
                text=text,
                spk_audio_prompt="role_audio/guo_08/guo_08_001.wav",
                emo_audio_prompt="role_audio/guo_08/guo_08_002.wav",
                output_path=f"outputs/batch_{i:02d}.wav",
            )
            params_list.append(params)

        # 执行批量克隆
        results = cloner.clone_batch(params_list)

        # 统计结果
        success_count = sum(1 for r in results if r.success)
        total_time = sum(r.duration_ms for r in results)

        print(f"\n批量克隆完成:")
        print(f"  成功: {success_count}/{len(results)}")
        print(f"  总耗时: {total_time}ms")
        print(f"  平均耗时: {total_time // len(results)}ms")

        # 显示详细结果
        for i, result in enumerate(results):
            status = "✅" if result.success else "❌"
            print(
                f"  {status} 任务 {i + 1}: {result.output_path if result.success else result.error_message}"
            )

    except Exception as e:
        print(f"❌ 测试失败: {e}")


def test_auto_output_path():
    """测试自动生成输出路径"""
    print("\n" + "=" * 70)
    print("测试4：自动生成输出路径")
    print("=" * 70)

    try:
        cloner = IndexTTS2VoiceCloner()

        # 不需要手动指定输出路径，系统会自动生成
        result = cloner.clone_with_auto_output_path(
            text="这是一个自动命名的测试音频文件。",
            spk_audio_prompt="role_audio/guo_08/guo_08_001.wav",
            emo_audio_prompt="role_audio/guo_08/guo_08_002.wav",
            output_dir="outputs/auto",
            output_prefix="test_auto",
        )

        if result.success:
            print(f"✅ 成功生成音频")
            print(f"   自动生成的文件路径: {result.output_path}")
        else:
            print(f"❌ 生成失败: {result.error_message}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")


def test_quick_functions():
    """测试快捷函数"""
    print("\n" + "=" * 70)
    print("测试5：使用快捷函数")
    print("=" * 70)

    try:
        # 快捷函数1：使用情感参考音频
        print("\n5.1 快捷克隆（情感音频）")
        success1 = quick_clone_with_emotion(
            text="这是快捷函数测试。",
            speaker_audio="role_audio/guo_08/guo_08_001.wav",
            emotion_audio="role_audio/guo_08/guo_08_002.wav",
            output_path="outputs/quick_emotion.wav",
        )
        print(f"  {'✅ 成功' if success1 else '❌ 失败'}")

        # 快捷函数2：使用情感向量
        print("\n5.2 快捷克隆（情感向量）")
        success2 = quick_clone_with_vector(
            text="使用向量控制情感。",
            speaker_audio="role_audio/guo_08/guo_08_001.wav",
            emotion_vector=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            output_path="outputs/quick_vector.wav",
            emo_alpha=0.6,
        )
        print(f"  {'✅ 成功' if success2 else '❌ 失败'}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")


def test_flexible_params():
    """测试灵活的参数配置"""
    print("\n" + "=" * 70)
    print("测试6：灵活的参数配置（VoiceCloneParams）")
    print("=" * 70)

    try:
        cloner = IndexTTS2VoiceCloner()

        # 使用 VoiceCloneParams 可以更灵活地配置参数
        params = VoiceCloneParams(
            text="使用参数类进行配置，更加灵活和类型安全。",
            spk_audio_prompt="role_audio/guo_08/guo_08_001.wav",
            emo_audio_prompt="role_audio/guo_08/guo_08_002.wav",
            output_path="outputs/flexible_params.wav",
            emo_alpha=0.65,
            verbose=True,
        )

        # 执行克隆
        result = cloner.clone(params)

        if result.success:
            print(f"✅ 成功生成音频")
            print(f"   输出文件: {result.output_path}")
        else:
            print(f"❌ 生成失败: {result.error_message}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")


def test_integration_with_story_generator():
    """演示如何集成到故事生成器中"""
    print("\n" + "=" * 70)
    print("测试7：集成到故事生成器（模拟）")
    print("=" * 70)

    try:
        # 模拟故事段落数据
        story_segments = [
            {
                "text": "很久很久以前，有一个美丽的王国。",
                "emotion": "平静",
                "spk_audio": "role_audio/guo_08/guo_08_001.wav",
                "emo_audio": "role_audio/guo_08/guo_08_005.wav",
            },
            {
                "text": "国王和王后非常善良，人们都很爱戴他们。",
                "emotion": "温暖",
                "spk_audio": "role_audio/guo_08/guo_08_001.wav",
                "emo_audio": "role_audio/guo_08/guo_08_006.wav",
            },
            {
                "text": "突然有一天，王国遭受了可怕的灾难！",
                "emotion": "惊恐",
                "spk_audio": "role_audio/guo_08/guo_08_001.wav",
                "emo_audio": "role_audio/guo_08/guo_08_007.wav",
            },
        ]

        cloner = IndexTTS2VoiceCloner()

        # 为每个段落生成音频
        for i, segment in enumerate(story_segments):
            print(f"\n处理段落 {i + 1}/{len(story_segments)}: {segment['emotion']}")

            result = cloner.clone_with_emotion_audio(
                text=segment["text"],
                spk_audio_prompt=segment["spk_audio"],
                emo_audio_prompt=segment["emo_audio"],
                output_path=f"outputs/story_segment_{i:02d}.wav",
                verbose=False,  # 关闭详细日志
            )

            if result.success:
                print(f"  ✅ 已生成: {result.output_path} ({result.duration_ms}ms)")
            else:
                print(f"  ❌ 失败: {result.error_message}")

        print("\n故事音频生成完成！")

    except Exception as e:
        print(f"❌ 测试失败: {e}")


def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("Index-TTS2 Voice Cloner 测试套件")
    print("=" * 70)

    # 确保输出目录存在
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("outputs/auto", exist_ok=True)

    # 运行所有测试
    tests = [
        ("基本用法", test_basic_usage),
        ("情感向量", test_emotion_vector),
        ("批量克隆", test_batch_clone),
        ("自动路径", test_auto_output_path),
        ("快捷函数", test_quick_functions),
        ("参数配置", test_flexible_params),
        ("故事集成", test_integration_with_story_generator),
    ]

    print("\n选择要运行的测试:")
    print("0. 运行所有测试")
    for i, (name, _) in enumerate(tests, 1):
        print(f"{i}. {name}")

    try:
        choice = input("\n请输入选项 (0-7, 默认0): ").strip()
        choice = int(choice) if choice else 0

        if choice == 0:
            # 运行所有测试
            for name, test_func in tests:
                try:
                    test_func()
                except Exception as e:
                    logger.error(f"测试 '{name}' 失败: {e}")
        elif 1 <= choice <= len(tests):
            # 运行指定测试
            name, test_func = tests[choice - 1]
            test_func()
        else:
            print("无效的选项")

    except (ValueError, KeyboardInterrupt):
        print("\n测试已取消")

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
