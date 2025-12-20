# AutoVoiceCloner 使用文档

## 📖 简介

`AutoVoiceCloner` 是一个自动化声音克隆工具类，封装了 `IndexTTS2VoiceCloner` 的功能，提供简洁的 API 接口用于批量或单条声音克隆任务。

---

## 🎯 核心功能

### 1. 批量克隆模式

从 JSON 配置文件读取任务列表，批量生成音频文件。

**特点**：

- ✅ 自动从 JSON 读取任务
- ✅ 按 `sort` 字段排序
- ✅ 支持进度显示
- ✅ 失败自动跳过，不影响后续任务

### 2. 单条克隆模式

快速生成单个音频文件，无需配置文件。

**特点**：

- ✅ 直接传参，快速执行
- ✅ 适合测试和简单场景

---

## 🚀 快速开始

### 安装依赖

```bash
pip install indextts
```

### 导入模块

```python
from scripts.auto_voice_cloner import AutoVoiceCloner
```

---

## 📝 使用示例

### 示例 1：批量克隆模式

```python
from scripts.auto_voice_cloner import AutoVoiceCloner

# 1. 创建克隆器实例
cloner = AutoVoiceCloner(output_dir="outputs/sherlock_holmes")

# 2. 执行批量克隆
result = cloner.run_cloning(
    input_audio="/path/to/narrator_voice.wav",              # 旁白音色
    batch_json_path="db/sherlock_holmes_narrator_01.json",  # JSON配置
    emo_audio_folder="/path/to/emotion_audios/"             # 情感音频文件夹
)

# 3. 查看结果
print(f"总任务数: {result['total']}")
print(f"成功: {result['success']}")
print(f"失败: {result['failed']}")
print(f"成功率: {result['success']/result['total']*100:.1f}%")
```

**JSON 配置文件格式**：

```json
[
  {
    "sort": 1,
    "text": "今年伦敦的春天似乎比往年来得早些",
    "emo_audio": "01-今年伦敦的春天似乎比往年来得早些.WAV"
  },
  {
    "sort": 2,
    "text": "大街上的人多了许多",
    "emo_audio": "02-大街上的人多了许多.WAV"
  }
]
```

**生成的文件**：

```
outputs/sherlock_holmes/
├── 1_今年伦敦的春天似乎比往年来得早些.wav
├── 2_大街上的人多了许多.wav
└── ...
```

---

### 示例 2：单条克隆模式

```python
from scripts.auto_voice_cloner import AutoVoiceCloner

# 1. 创建克隆器实例
cloner = AutoVoiceCloner(output_dir="outputs/test")

# 2. 执行单条克隆
result = cloner.run_cloning(
    input_audio="speaker.wav",      # 说话人音色
    emo_audio="happy_emotion.wav",  # 情感参考
    emo_text="你好，今天天气真好！"  # 要生成的文本
)

# 3. 查看结果
if result['success']:
    print(f"✅ 生成成功: {result['results'][0]['output_path']}")
else:
    print(f"❌ 生成失败: {result['results'][0]['error']}")
```

**生成的文件**：

```
outputs/test/single_你好今天天气真好.wav
```

---

## 🔧 API 参考

### 类：AutoVoiceCloner

#### 构造函数

```python
AutoVoiceCloner(
    output_dir: str = "outputs",
    cfg_path: Optional[str] = None,
    model_dir: Optional[str] = None
)
```

**参数**：

- `output_dir` (str): 输出目录，默认 "outputs"
- `cfg_path` (Optional[str]): TTS 模型配置文件路径
- `model_dir` (Optional[str]): TTS 模型目录路径

---

#### 方法：run_cloning()

```python
run_cloning(
    input_audio: str,
    batch_json_path: Optional[str] = None,
    emo_audio_folder: Optional[str] = None,
    emo_audio: Optional[str] = None,
    emo_text: Optional[str] = None
) -> Dict
```

**参数说明**：

| 参数               | 类型 | 必需            | 说明                   |
| ------------------ | ---- | --------------- | ---------------------- |
| `input_audio`      | str  | ✅ 是           | 说话人音色参考音频路径 |
| `batch_json_path`  | str  | ⚠️ 批量模式必需 | JSON 配置文件路径      |
| `emo_audio_folder` | str  | ⚠️ 批量模式可选 | 情感音频文件夹路径     |
| `emo_audio`        | str  | ⚠️ 单条模式必需 | 情感参考音频路径       |
| `emo_text`         | str  | ⚠️ 单条模式必需 | 要生成的文本内容       |

**模式判断**：

- 如果 `batch_json_path` **不为空** → 批量克隆模式
- 如果 `batch_json_path` **为空** → 单条克隆模式

**返回值**：

```python
{
    'mode': 'batch' 或 'single',  # 执行模式
    'total': int,                  # 总任务数
    'success': int,                # 成功数量
    'failed': int,                 # 失败数量
    'results': [                   # 详细结果列表
        {
            'sort': int,           # 序号（仅批量模式）
            'text': str,           # 文本内容
            'output_path': str,    # 输出路径
            'success': bool,       # 是否成功
            'error': str,          # 错误信息（如果失败）
            'duration_ms': int     # 耗时（毫秒）
        },
        ...
    ]
}
```

---

## 📋 完整示例

### 福尔摩斯旁白生成

```python
#!/usr/bin/env python3
"""
福尔摩斯故事旁白音频生成脚本
"""

from scripts.auto_voice_cloner import AutoVoiceCloner
import json

def main():
    # 配置路径
    NARRATOR_VOICE = "role_audio/narrator_voice_sample.wav"
    JSON_CONFIG = "db/sherlock_holmes_narrator_01.json"
    EMO_AUDIO_FOLDER = "role_audio/福尔摩斯第一集原人声切片/旁白"
    OUTPUT_DIR = "outputs/sherlock_holmes_ep01/narrator"

    print("="*70)
    print("福尔摩斯故事旁白音频生成")
    print("="*70)

    # 创建克隆器
    cloner = AutoVoiceCloner(output_dir=OUTPUT_DIR)

    # 执行批量克隆
    result = cloner.run_cloning(
        input_audio=NARRATOR_VOICE,
        batch_json_path=JSON_CONFIG,
        emo_audio_folder=EMO_AUDIO_FOLDER
    )

    # 保存结果报告
    with open(f"{OUTPUT_DIR}/generation_report.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 输出统计
    print(f"\n生成完成！")
    print(f"  总计: {result['total']} 个")
    print(f"  成功: {result['success']} 个")
    print(f"  失败: {result['failed']} 个")
    print(f"  成功率: {result['success']/result['total']*100:.1f}%")

    # 列出失败的任务
    if result['failed'] > 0:
        print(f"\n失败的任务:")
        for r in result['results']:
            if not r['success']:
                print(f"  - 序号 {r.get('sort', '?')}: {r.get('error', '未知错误')}")

if __name__ == "__main__":
    main()
```

---

## ⚠️ 注意事项

### 1. 文件名清洗

为了避免文件系统错误，工具会自动清洗文本中的非法字符：

**清洗规则**：

- 移除 Windows 非法字符：`< > : " / \ | ? *`
- 替换为下划线 `_`
- 移除 `llm_` 开头的时间戳标记
- 限制最大长度为 50 个字符

**示例**：

```
原始文本: llm_002_3.9s_一个个看上去神清气爽，精神熠熠
清洗后:   一个个看上去神清气爽_精神熠熠
```

### 2. JSON 字段说明

JSON 配置文件必须包含以下字段：

| 字段                      | 类型 | 必需 | 说明           |
| ------------------------- | ---- | ---- | -------------- |
| `sort` 或 `id`            | int  | ✅   | 排序序号       |
| `text`                    | str  | ✅   | 文本内容       |
| `emo_audio` 或 `filename` | str  | ✅   | 情感音频文件名 |

### 3. 路径处理

- 所有路径支持相对路径和绝对路径
- `emo_audio_folder` + `emo_audio` = 完整音频路径
- 输出路径自动创建，无需手动创建目录

---

## 🐛 常见问题

### Q1: ModuleNotFoundError: No module named 'indextts'

**解决方案**：

```bash
pip install indextts
```

### Q2: FileNotFoundError: 音频文件不存在

**原因**：情感音频路径配置错误

**解决方案**：

1. 检查 `emo_audio_folder` 路径是否正确
2. 检查 JSON 中的 `emo_audio` 文件名是否正确
3. 确认文件确实存在

### Q3: 批量克隆部分失败

**原因**：某些音频文件缺失或损坏

**解决方案**：

- 查看日志中的错误信息
- 检查失败任务的文件路径
- 批量克隆会自动跳过失败任务，不影响其他任务

---

## 📊 性能优化

### 1. 批量处理建议

```python
# ✅ 推荐：复用同一个克隆器实例
cloner = AutoVoiceCloner()
result1 = cloner.run_cloning(...)  # 第一批
result2 = cloner.run_cloning(...)  # 第二批

# ❌ 不推荐：每次都创建新实例
for task in tasks:
    cloner = AutoVoiceCloner()  # 重复加载模型
    cloner.run_cloning(...)
```

### 2. 日志控制

批量模式下，工具会自动关闭详细日志以提高性能。如需调试，可以修改源码：

```python
result = self.cloner.clone_with_emotion_audio(
    ...,
    verbose=True  # 改为True启用详细日志
)
```

---

## 📄 许可证

本工具基于 IndexTTS2VoiceCloner 开发，遵循相同的许可协议。

---

**最后更新**: 2025-12-20  
**版本**: 1.0.0
