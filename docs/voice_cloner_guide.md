# Index-TTS2 Voice Cloner 使用指南

## 📖 概述

`IndexTTS2VoiceCloner` 是一个专业的声音克隆工具类，封装了 Index-TTS2 模型的调用逻辑，提供了简洁、类型安全的 API 接口。

### ✨ 主要特性

- ✅ **双模式支持**：情感参考音频模式 + 情感向量模式
- ✅ **类型安全**：使用 `dataclass` 进行参数验证
- ✅ **错误处理**：完善的异常捕获和错误提示
- ✅ **批量处理**：支持批量生成音频
- ✅ **自动化**：自动创建输出目录、自动生成文件名
- ✅ **灵活配置**：多种调用方式，适应不同场景

---

## 🚀 快速开始

### 1. 基本导入

```python
from scripts.index_tts2_voice_cloner import (
    IndexTTS2VoiceCloner,
    VoiceCloneParams,
    CloneResult
)
```

### 2. 创建克隆器实例

```python
# 使用默认配置
cloner = IndexTTS2VoiceCloner()

# 或者自定义配置
cloner = IndexTTS2VoiceCloner(
    cfg_path="/path/to/config.yaml",
    model_dir="/path/to/models",
    auto_create_output_dir=True
)
```

### 3. 执行声音克隆

#### 方式 1：使用情感参考音频（推荐）

```python
result = cloner.clone_with_emotion_audio(
    text="你好，今天天气真好！",
    spk_audio_prompt="speaker.wav",      # 音色来源
    emo_audio_prompt="happy_emotion.wav", # 情感来源
    output_path="output.wav"
)

if result.success:
    print(f"成功！文件: {result.output_path}")
else:
    print(f"失败: {result.error_message}")
```

#### 方式 2：使用情感向量

```python
result = cloner.clone_with_emotion_vector(
    text="我很开心！",
    spk_audio_prompt="speaker.wav",
    emo_vector=[0.8, 0.2, 0.1, 0.3, 0.5, 0.4, 0.6, 0.7],
    emo_alpha=0.7,
    output_path="output.wav"
)
```

#### 方式 3：使用参数类（更灵活）

```python
params = VoiceCloneParams(
    text="测试文本",
    spk_audio_prompt="speaker.wav",
    emo_audio_prompt="emotion.wav",
    output_path="output.wav",
    emo_alpha=0.65,
    verbose=True
)

result = cloner.clone(params)
```

---

## 📚 详细 API 文档

### 类：IndexTTS2VoiceCloner

主要的声音克隆器类。

#### 构造函数

```python
IndexTTS2VoiceCloner(
    cfg_path: Optional[str] = None,
    model_dir: Optional[str] = None,
    auto_create_output_dir: bool = True
)
```

**参数说明：**

- `cfg_path`: TTS 模型配置文件路径（可选）
- `model_dir`: TTS 模型目录路径（可选）
- `auto_create_output_dir`: 是否自动创建输出目录

#### 主要方法

##### 1. clone_with_emotion_audio()

使用情感参考音频进行克隆。

```python
clone_with_emotion_audio(
    text: str,
    spk_audio_prompt: str,
    emo_audio_prompt: str,
    output_path: str,
    verbose: bool = True
) -> CloneResult
```

**适用场景：**

- ✅ 有现成的情感参考音频
- ✅ 需要迁移特定情感特征
- ✅ 最常用的克隆方式

**示例：**

```python
result = cloner.clone_with_emotion_audio(
    text="今天真是美好的一天！",
    spk_audio_prompt="role_audio/alice.wav",
    emo_audio_prompt="emotion_samples/happy.wav",
    output_path="outputs/result.wav"
)
```

##### 2. clone_with_emotion_vector()

使用情感向量进行克隆。

```python
clone_with_emotion_vector(
    text: str,
    spk_audio_prompt: str,
    emo_vector: List[float],
    output_path: str,
    emo_alpha: float = 0.65,
    verbose: bool = True
) -> CloneResult
```

**适用场景：**

- ✅ 需要精确控制情感参数
- ✅ 已经提取了情感向量
- ✅ 做情感实验和调优

**参数说明：**

- `emo_vector`: 8 维浮点数列表，表示情感向量
- `emo_alpha`: 情感混合系数 [0.0, 1.0]
  - 0.0 = 完全不使用情感
  - 1.0 = 完全使用情感
  - 0.65 = 推荐默认值（平衡）

**示例：**

```python
result = cloner.clone_with_emotion_vector(
    text="我很开心！",
    spk_audio_prompt="speaker.wav",
    emo_vector=[0.8, 0.2, 0.1, 0.3, 0.5, 0.4, 0.6, 0.7],
    emo_alpha=0.7,
    output_path="output.wav"
)
```

##### 3. clone_batch()

批量克隆多个音频。

```python
clone_batch(
    params_list: List[VoiceCloneParams]
) -> List[CloneResult]
```

**特点：**

- ✅ 即使某个任务失败，也会继续处理后续任务
- ✅ 返回所有任务的结果列表
- ✅ 适合批量生成故事音频

**示例：**

```python
params_list = [
    VoiceCloneParams(
        text="第一句话",
        spk_audio_prompt="speaker.wav",
        emo_audio_prompt="happy.wav",
        output_path="output1.wav"
    ),
    VoiceCloneParams(
        text="第二句话",
        spk_audio_prompt="speaker.wav",
        emo_audio_prompt="sad.wav",
        output_path="output2.wav"
    ),
]

results = cloner.clone_batch(params_list)
success_count = sum(1 for r in results if r.success)
print(f"成功: {success_count}/{len(results)}")
```

##### 4. clone_with_auto_output_path()

自动生成输出路径。

```python
clone_with_auto_output_path(
    text: str,
    spk_audio_prompt: str,
    emo_audio_prompt: Optional[str] = None,
    emo_vector: Optional[List[float]] = None,
    emo_alpha: float = 0.65,
    output_dir: str = "outputs",
    output_prefix: str = "clone",
    verbose: bool = True
) -> CloneResult
```

**特点：**

- ✅ 不需要手动指定输出文件名
- ✅ 自动生成带时间戳的文件名
- ✅ 格式：`{prefix}_{timestamp}.wav`

**示例：**

```python
result = cloner.clone_with_auto_output_path(
    text="自动命名测试",
    spk_audio_prompt="speaker.wav",
    emo_audio_prompt="emotion.wav",
    output_dir="my_outputs",
    output_prefix="test"
)
# 生成文件：my_outputs/test_1703123456789.wav
```

---

## 🎯 使用场景示例

### 场景 1：故事书生成器集成

```python
from scripts.index_tts2_voice_cloner import IndexTTS2VoiceCloner

class StoryBookGenerator:
    def __init__(self):
        self.cloner = IndexTTS2VoiceCloner()

    def generate_story_audio(self, story_segments):
        """生成故事音频"""
        audio_files = []

        for segment in story_segments:
            result = self.cloner.clone_with_emotion_audio(
                text=segment["text"],
                spk_audio_prompt=segment["speaker_audio"],
                emo_audio_prompt=segment["emotion_audio"],
                output_path=segment["output_path"]
            )

            if result.success:
                audio_files.append(result.output_path)
            else:
                print(f"警告: 生成失败 - {result.error_message}")

        return audio_files
```

### 场景 2：批量情感实验

```python
# 测试不同情感混合系数
cloner = IndexTTS2VoiceCloner()

alphas = [0.3, 0.5, 0.7, 0.9]
for alpha in alphas:
    result = cloner.clone_with_emotion_vector(
        text="这是情感实验测试。",
        spk_audio_prompt="speaker.wav",
        emo_vector=[0.8] * 8,
        emo_alpha=alpha,
        output_path=f"outputs/exp_alpha_{alpha}.wav"
    )
    print(f"Alpha={alpha}: {'成功' if result.success else '失败'}")
```

### 场景 3：简单快捷调用

```python
from scripts.index_tts2_voice_cloner import quick_clone_with_emotion

# 一行代码完成克隆
success = quick_clone_with_emotion(
    text="快速测试",
    speaker_audio="speaker.wav",
    emotion_audio="happy.wav",
    output_path="output.wav"
)
```

---

## 🔧 高级配置

### 情感向量说明

情感向量是 8 维向量，每个维度代表不同的情感特征：

```python
emo_vector = [
    0.5,  # 维度1: 情感强度
    0.5,  # 维度2: 音调变化
    0.5,  # 维度3: 语速控制
    0.5,  # 维度4: 音量变化
    0.5,  # 维度5: 停顿控制
    0.5,  # 维度6: 音色明暗
    0.5,  # 维度7: 共鸣腔体
    0.5   # 维度8: 气息控制
]
```

**调优建议：**

- 初始值：全部设为 0.5（中性）
- 调整范围：[0.0, 1.0]
- 步长：0.1 或 0.2
- 建议先调整前 3 个维度

### 情感混合系数（emo_alpha）

```python
emo_alpha = 0.0   # 完全不使用情感特征
emo_alpha = 0.3   # 轻微情感
emo_alpha = 0.5   # 中等情感
emo_alpha = 0.65  # 推荐默认值
emo_alpha = 0.8   # 强情感
emo_alpha = 1.0   # 极强情感
```

---

## ⚠️ 错误处理

### 常见错误及解决方案

#### 1. RuntimeError: TTS 功能不可用

**原因：** 未安装 indextts 包

**解决：**

```bash
pip install indextts
```

#### 2. FileNotFoundError: 音频文件不存在

**原因：** 指定的音频文件路径不存在

**解决：**

```python
import os
# 使用前检查文件是否存在
if not os.path.exists("speaker.wav"):
    print("文件不存在！")
```

#### 3. ValueError: emo_vector 必须是长度为 8 的向量

**原因：** 情感向量维度不正确

**解决：**

```python
# 确保向量是8维
emo_vector = [0.5] * 8  # 创建8维向量
```

#### 4. 生成的音频文件过小

**原因：** 模型推理失败或输入参数错误

**解决：**

- 检查输入音频文件是否有效
- 检查文本内容是否为空
- 查看详细日志（设置 `verbose=True`）

---

## 📊 性能优化建议

### 1. 批量处理优化

```python
# ✅ 推荐：使用批量处理
results = cloner.clone_batch(params_list)

# ❌ 不推荐：循环中重复创建实例
for params in params_list:
    cloner = IndexTTS2VoiceCloner()  # 每次都重新加载模型！
    result = cloner.clone(params)
```

### 2. 模型复用

```python
# ✅ 推荐：复用同一个实例
cloner = IndexTTS2VoiceCloner()
for i in range(100):
    result = cloner.clone_with_emotion_audio(...)

# ❌ 不推荐：每次都创建新实例
for i in range(100):
    cloner = IndexTTS2VoiceCloner()
    result = cloner.clone_with_emotion_audio(...)
```

### 3. 关闭详细日志

```python
# 批量处理时关闭详细日志以提高性能
result = cloner.clone_with_emotion_audio(
    ...,
    verbose=False  # 关闭详细日志
)
```

---

## 🧪 完整示例代码

### 示例 1：故事播客生成

```python
from scripts.index_tts2_voice_cloner import IndexTTS2VoiceCloner, VoiceCloneParams

def generate_podcast():
    """生成播客音频"""
    cloner = IndexTTS2VoiceCloner()

    # 播客脚本
    script = [
        ("欢迎收听今天的节目！", "role_audio/host.wav", "emotion/excited.wav"),
        ("今天我们要聊聊人工智能的发展。", "role_audio/host.wav", "emotion/calm.wav"),
        ("让我们先听听嘉宾的看法。", "role_audio/host.wav", "emotion/curious.wav"),
        ("我认为AI将改变世界。", "role_audio/guest.wav", "emotion/confident.wav"),
    ]

    audio_files = []
    for i, (text, speaker, emotion) in enumerate(script):
        result = cloner.clone_with_emotion_audio(
            text=text,
            spk_audio_prompt=speaker,
            emo_audio_prompt=emotion,
            output_path=f"podcast/segment_{i:03d}.wav",
            verbose=False
        )

        if result.success:
            audio_files.append(result.output_path)
            print(f"✅ 片段 {i+1} 完成")

    print(f"\n播客生成完成！共 {len(audio_files)} 个片段")
    return audio_files

if __name__ == "__main__":
    generate_podcast()
```

### 示例 2：多语言支持

```python
def multilingual_generation():
    """多语言生成示例"""
    cloner = IndexTTS2VoiceCloner()

    texts = {
        "中文": "你好，世界！",
        "英文": "Hello, World!",
        "日文": "こんにちは、世界！"
    }

    for lang, text in texts.items():
        result = cloner.clone_with_auto_output_path(
            text=text,
            spk_audio_prompt="speaker_multilingual.wav",
            emo_audio_prompt="emotion_neutral.wav",
            output_prefix=f"multilingual_{lang}"
        )

        if result.success:
            print(f"✅ {lang}: {result.output_path}")
```

---

## 📝 最佳实践

### ✅ DO（推荐做法）

1. **复用克隆器实例**

   ```python
   cloner = IndexTTS2VoiceCloner()
   for text in texts:
       result = cloner.clone_with_emotion_audio(...)
   ```

2. **使用参数类进行复杂配置**

   ```python
   params = VoiceCloneParams(...)
   result = cloner.clone(params)
   ```

3. **批量处理使用 clone_batch()**

   ```python
   results = cloner.clone_batch(params_list)
   ```

4. **检查结果状态**
   ```python
   if result.success:
       print(f"成功: {result.output_path}")
   else:
       print(f"失败: {result.error_message}")
   ```

### ❌ DON'T（避免的做法）

1. **不要在循环中重复创建实例**

   ```python
   # ❌ 性能很差
   for text in texts:
       cloner = IndexTTS2VoiceCloner()
       result = cloner.clone_with_emotion_audio(...)
   ```

2. **不要忽略错误结果**

   ```python
   # ❌ 可能会导致后续处理失败
   result = cloner.clone_with_emotion_audio(...)
   # 直接使用 result.output_path 而不检查 result.success
   ```

3. **不要使用无效的情感向量**
   ```python
   # ❌ 错误：向量维度不是8
   emo_vector = [0.5, 0.6, 0.7]
   ```

---

## 🎓 进阶话题

### 自定义克隆器

```python
class MyCustomCloner(IndexTTS2VoiceCloner):
    """自定义克隆器，添加额外功能"""

    def clone_with_preprocessing(self, text, **kwargs):
        """克隆前预处理文本"""
        # 文本清洗
        text = self.clean_text(text)

        # 调用父类方法
        return super().clone_with_emotion_audio(text=text, **kwargs)

    def clean_text(self, text):
        """文本清洗逻辑"""
        # 移除特殊字符
        # 标准化标点
        # ...
        return text
```

---

## 📞 技术支持

如有问题，请：

1. 查看本文档的"错误处理"部分
2. 运行 `test_voice_cloner.py` 进行测试
3. 检查日志输出（设置 `verbose=True`）
4. 联系开发团队

---

**文档版本：** v1.0  
**最后更新：** 2025-12-20  
**维护者：** AI Assistant
