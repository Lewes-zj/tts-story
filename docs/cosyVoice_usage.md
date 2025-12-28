# CosyVoice 声音复刻 API 使用指南

## 快速开始

### 1. 安装依赖

```bash
pip install dashscope>=1.17.0
```

或者安装所有依赖：

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

**方式1: 环境变量（推荐）**

```bash
export DASHSCOPE_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**方式2: 代码中传入**

```python
from scripts.cosyVoice import CosyVoiceService

service = CosyVoiceService(api_key="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
```

### 3. 基本调用示例

#### 示例1: 创建音色并合成语音

```python
from scripts.cosyVoice import CosyVoiceService, TargetModel

# 初始化服务
service = CosyVoiceService()

# 创建音色（需要公网可访问的音频 URL）
voice_info = service.create_voice(
    target_model=TargetModel.COSYVOICE_V3_PLUS.value,
    prefix="myvoice",
    audio_url="https://your-audio-url.com/sample.wav",
    description="我的自定义音色"
)

print(f"音色创建成功: {voice_info.voice_id}")

# 使用音色进行语音合成
service.synthesize_speech_to_file(
    text="你好，这是使用复刻音色合成的语音。",
    output_path="output.wav",
    voice_id=voice_info.voice_id
)
```

#### 示例2: 使用已存在的音色

```python
from scripts.cosyVoice import CosyVoiceService

service = CosyVoiceService()

# 查询音色列表
voices = service.list_voices()
if voices:
    voice_id = voices[0].voice_id
    
    # 使用音色进行合成
    service.synthesize_speech_to_file(
        text="你好，世界！",
        output_path="output.wav",
        voice_id=voice_id
    )
```

#### 示例3: 查询音色详情

```python
from scripts.cosyVoice import CosyVoiceService

service = CosyVoiceService()

# 查询音色详情
voice_info = service.get_voice("cosyvoice-v3-plus-myvoice-xxx")
print(f"状态: {voice_info.status}")
print(f"模型: {voice_info.target_model}")
print(f"描述: {voice_info.description}")
```

## 完整 API 参考

### CosyVoiceService 类

#### 初始化

```python
service = CosyVoiceService(api_key=None)
```

- `api_key`: DashScope API Key，如果为 None 则从环境变量 `DASHSCOPE_API_KEY` 读取

#### 音色管理方法

##### create_voice() - 创建音色

```python
voice_info = service.create_voice(
    target_model: str,              # 语音合成模型: cosyvoice-v1/v2/v3-flash/v3-plus
    prefix: str,                    # 音色前缀（数字和小写字母，<10字符）
    audio_url: Optional[str] = None, # 公网可访问的音频 URL
    audio_file: Optional[str] = None, # 本地音频文件（需要先上传）
    description: Optional[str] = None, # 音色描述
    wait_for_completion: bool = True,  # 是否等待创建完成
    timeout: int = 300               # 等待超时时间（秒）
)
```

**返回**: `VoiceInfo` 对象

##### list_voices() - 查询音色列表

```python
voices = service.list_voices(
    target_model: Optional[str] = None,  # 按模型筛选
    prefix: Optional[str] = None         # 按前缀筛选
)
```

**返回**: `List[VoiceInfo]`

##### get_voice() - 查询音色详情

```python
voice_info = service.get_voice(voice_id: str)
```

**返回**: `VoiceInfo` 对象

##### update_voice() - 更新音色

```python
voice_info = service.update_voice(
    voice_id: str,
    description: Optional[str] = None,
    audio_url: Optional[str] = None
)
```

**返回**: `VoiceInfo` 对象

##### delete_voice() - 删除音色

```python
success = service.delete_voice(voice_id: str)
```

**返回**: `bool`

#### 语音合成方法

##### synthesize_speech() - 语音合成

```python
result = service.synthesize_speech(
    text: str,                      # 要合成的文本
    voice_id: Optional[str] = None, # 复刻音色 ID
    model: Optional[str] = None,    # 语音合成模型（必须与创建音色时一致）
    speech_rate: Optional[float] = None,  # 语速 (0.5-2.0)
    volume: Optional[float] = None,        # 音量 (0.0-1.0)
    pitch: Optional[float] = None,         # 音调
    format: str = "wav",                   # 输出格式: wav/mp3/m4a
    sample_rate: int = 24000               # 采样率
)
```

**返回**: `SpeechSynthesisResponse` 对象（包含 `audio_data` 字节数据）

##### synthesize_speech_to_file() - 合成并保存到文件

```python
output_path = service.synthesize_speech_to_file(
    text: str,
    output_path: str,
    voice_id: Optional[str] = None,
    model: Optional[str] = None,
    speech_rate: Optional[float] = None,
    volume: Optional[float] = None,
    pitch: Optional[float] = None,
    format: str = "wav",
    sample_rate: int = 24000
)
```

**返回**: 输出文件路径（str）

## 运行示例脚本

项目提供了完整的示例脚本，展示各种使用场景：

```bash
python scripts/cosyVoice_example.py
```

示例脚本包含以下场景：
1. 基本使用流程（创建音色 + 语音合成）
2. 查询音色列表
3. 查询音色详情
4. 使用不同参数进行语音合成
5. 更新音色信息
6. 异步创建音色
7. 使用已存在的音色

## 支持的模型

| 模型 | 说明 | 适用场景 |
|------|------|----------|
| `cosyvoice-v3-plus` | 最佳音质 | 追求最佳效果，预算充足（推荐） |
| `cosyvoice-v3-flash` | 平衡效果与成本 | 综合性价比高 |
| `cosyvoice-v2` | 兼容旧版 | 兼容旧版或低要求场景 |
| `cosyvoice-v1` | 兼容旧版 | 兼容旧版或低要求场景 |

## 音频要求

创建音色时，音频文件需要满足以下要求：

- **格式**: WAV (16bit), MP3, M4A
- **时长**: 推荐 10-20 秒，最长 60 秒
- **大小**: ≤ 10 MB
- **采样率**: ≥ 16 kHz
- **内容**: 
  - 至少 5 秒连续清晰朗读（无背景音）
  - 其余部分仅允许短暂停顿（≤2秒）
  - 避免背景音乐、噪音或其他人声
  - 使用正常说话音频，不要使用歌曲或唱歌音频

## 重要提示

1. **模型一致性**: 创建音色时的 `target_model` 必须与语音合成时的 `model` 一致
2. **音色配额**: 每个账号最多 1000 个音色
3. **自动清理**: 一年内未使用的音色会自动删除
4. **音频 URL**: 必须公网可访问，建议使用阿里云 OSS 等对象存储服务

## 错误处理

所有方法都会抛出相应的异常，建议使用 try-except 进行错误处理：

```python
from scripts.cosyVoice import CosyVoiceService
from dashscope.common.error import AuthenticationError, InvalidInputError

try:
    service = CosyVoiceService()
    voice_info = service.create_voice(...)
except AuthenticationError:
    print("API Key 认证失败")
except InvalidInputError:
    print("输入参数无效")
except Exception as e:
    print(f"其他错误: {e}")
```

## 更多信息

- [阿里云 CosyVoice 官方文档](https://help.aliyun.com/zh/model-studio/cosyvoice-clone-api)
- [DashScope SDK 文档](https://help.aliyun.com/zh/model-studio/developer-reference/api-details-9)

