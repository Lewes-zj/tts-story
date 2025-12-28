# CosyVoice V3 使用说明（初学者版）

## 📖 什么是这个脚本？

这个脚本可以将一段音频的音色"克隆"出来，然后用这个音色来合成新的语音。

## ⚡ 快速开始（3 步）

```bash
# 1. 设置API Key（只需一次）
export DASHSCOPE_API_KEY="sk-your-api-key-here"

# 2. 运行脚本（替换为你的实际参数）
python cosyvoice_v3.py \
  --audio-url "https://your-audio-url.com/sample.wav" \
  --text "你想说的话"

# 3. 等待完成，音频会自动保存到 outputs/cosyvoice_output.mp3
```

就这么简单！🎉

## 🚀 最简单的使用方法

### 方法 1: 使用命令行参数运行（推荐，最简单）

1. **设置 API Key**（只需设置一次）

   在终端中运行（macOS/Linux）：

   ```bash
   export DASHSCOPE_API_KEY="sk-your-api-key-here"
   ```

   或者 Windows PowerShell：

   ```powershell
   $env:DASHSCOPE_API_KEY="sk-your-api-key-here"
   ```

   > 💡 提示：每次重新打开终端都需要重新设置。如果想永久保存，可以添加到系统环境变量中。

2. **运行脚本并传入参数**

   在终端中进入脚本所在目录，然后运行：

   ```bash
   python cosyvoice_v3.py --audio-url "https://your-audio-url.com/sample.wav" --text "你想说的话" --output "outputs/my_output.mp3"
   ```

   **参数说明**：

   - `--audio-url`: 你的音频文件网址（**必需**，必须是公网可以访问的）
   - `--text`: 你想让 AI 说的话（**必需**）
   - `--output`: 输出文件路径（**可选**，默认是 `outputs/cosyvoice_output.mp3`）

3. **完整示例**

   ```bash
   # 基本用法
   python cosyvoice_v3.py \
     --audio-url "https://example.com/my-voice.wav" \
     --text "大家好，我是AI助手"

   # 指定输出文件
   python cosyvoice_v3.py \
     --audio-url "https://example.com/my-voice.wav" \
     --text "大家好，我是AI助手" \
     --output "outputs/my_result.mp3"

   # 如果没设置环境变量，可以通过参数传入API Key
   python cosyvoice_v3.py \
     --api-key "sk-your-api-key-here" \
     --audio-url "https://example.com/my-voice.wav" \
     --text "大家好"
   ```

4. **查看帮助信息**

   如果想查看所有可用参数：

   ```bash
   python cosyvoice_v3.py --help
   ```

5. **等待完成**

   脚本会自动完成以下步骤：

   - 上传音频并创建音色
   - 等待音色处理完成（可能需要 1-5 分钟）
   - 使用音色合成语音
   - 保存音频文件

### 方法 2: 在其他 Python 文件中使用

如果你想把功能集成到其他 Python 程序中：

1. **在同一目录下创建新文件**，例如 `my_script.py`

2. **在新文件中写入以下代码**：

   ```python
   # 导入 CosyVoiceV3 类
   from cosyvoice_v3 import CosyVoiceV3

   # 创建客户端（会自动读取环境变量中的 API Key）
   client = CosyVoiceV3()

   # 调用合成方法
   audio_data = client.synthesize(
       audio_url="https://your-audio-url.com/sample.wav",
       text_to_synthesize="你想说的话",
       output_file="outputs/my_output.mp3"
   )

   print("完成！")
   ```

3. **运行你的脚本**：
   ```bash
   python my_script.py
   ```

## 📝 参数说明

### 命令行参数

#### `--audio-url` 或 `--audio_url` (必需)

- **作用**: 用于克隆音色的音频文件地址
- **要求**:
  - 必须是公网可以访问的网址（如 https://...）
  - 支持 .wav, .mp3 等常见音频格式
  - 音频质量越好，克隆效果越好
- **示例**: `--audio-url "https://example.com/my-voice.wav"`

#### `--text` 或 `--text-to-synthesize` (必需)

- **作用**: 你想让 AI 用克隆的音色说出来的话
- **要求**: 普通文本即可
- **示例**: `--text "大家好，我是AI助手"`

#### `--output` 或 `--output-file` (可选)

- **作用**: 合成后的音频保存位置
- **默认值**: `outputs/cosyvoice_output.mp3`
- **要求**: 文件路径，会自动创建目录
- **示例**: `--output "outputs/my_voice.mp3"`

#### `--api-key` (可选)

- **作用**: DashScope API Key
- **默认值**: 从环境变量 `DASHSCOPE_API_KEY` 读取
- **示例**: `--api-key "sk-your-api-key-here"`
- **注意**: 如果设置了环境变量，可以省略此参数

#### `--voice-prefix` (可选)

- **作用**: 音色前缀（仅允许数字和小写字母，小于十个字符）
- **默认值**: `"lxvoice"`
- **示例**: `--voice-prefix "myvoice"`

#### `--max-attempts` (可选)

- **作用**: 轮询最大尝试次数
- **默认值**: `30`
- **示例**: `--max-attempts 60`

#### `--poll-interval` (可选)

- **作用**: 轮询间隔秒数
- **默认值**: `10`
- **示例**: `--poll-interval 5`

## ⚙️ 高级配置（可选）

如果你需要自定义更多参数，可以在创建客户端时设置：

```python
client = CosyVoiceV3(
    api_key="sk-your-key",        # API Key（如果不设置，会从环境变量读取）
    target_model="cosyvoice-v3-plus",  # 模型名称（一般不需要改）
    voice_prefix="myvoice",        # 音色前缀（可选）
    max_attempts=30,               # 最大等待次数
    poll_interval=10               # 每次检查的间隔（秒）
)
```

## ❓ 常见问题

### 1. 提示 "API key is required"

**解决方法**:

- 确认已经设置了环境变量 `DASHSCOPE_API_KEY`
- 或者在代码中直接设置 `api_key = "你的key"`

### 2. 提示 "Voice processing failed"

**可能原因**:

- 音频文件质量不好
- 音频 URL 无法访问
- 音频格式不支持

**解决方法**:

- 确保音频 URL 是公网可访问的
- 使用清晰的音频文件
- 检查音频格式是否支持

### 3. 等待时间很长

**说明**:

- 音色处理通常需要 1-5 分钟，这是正常的
- 脚本会自动等待，你只需要耐心等待

### 4. 如何获取公网可访问的音频 URL？

**方法**:

- 上传到云存储（如阿里云 OSS、腾讯云 COS 等）
- 上传到 GitHub 仓库（需要是公开的）
- 使用文件托管服务

## 📚 更多帮助

如果遇到问题：

1. 检查错误信息，通常会有提示
2. 确认网络连接正常
3. 确认 API Key 有效
4. 查看脚本输出的详细信息
