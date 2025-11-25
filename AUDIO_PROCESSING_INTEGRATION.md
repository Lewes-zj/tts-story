# 音频处理集成说明

## 概述

本项目已集成 DeepFilterNet -> Denoiser 两步音频处理流程，当用户创建角色并上传音频时，系统会自动进行降噪和去混响处理。

## 架构说明

### 两个虚拟环境

1. **tts-story 项目环境**
   - 位置：`tts-story/venv/`（如果存在）
   - 用途：运行 FastAPI 服务

2. **extract-vocals 项目环境**
   - 位置：`/root/autodl-tmp/extract-vocals/venv/`
   - 用途：运行 DeepFilterNet 和 Denoiser 处理

### 集成方式

通过 `subprocess` 调用独立的音频处理服务脚本，实现跨虚拟环境的调用。

## 文件说明

### 1. 音频处理服务脚本
- **位置**：`/root/autodl-tmp/extract-vocals/audio_processor_service.py`
- **功能**：封装音频处理逻辑，可被其他项目调用
- **使用方式**：
  ```bash
  python3 /root/autodl-tmp/extract-vocals/audio_processor_service.py input.wav output.wav
  ```

### 2. tts-story 音频处理模块
- **位置**：`tts-story/scripts/audio_processor.py`
- **功能**：调用 extract-vocals 环境中的处理服务
- **主要函数**：`process_audio_with_deepfilternet_denoiser()`

### 3. 角色创建 API
- **位置**：`tts-story/scripts/character_api.py`
- **修改**：在保存角色时自动处理音频
- **流程**：
  1. 用户上传音频文件
  2. 创建角色时，调用音频处理
  3. 保存处理后的音频路径到 `clean_input` 字段

## 环境变量配置

### EXTRACT_VOCALS_DIR

设置 extract-vocals 项目的路径（如果不在默认位置）：

```bash
export EXTRACT_VOCALS_DIR=/path/to/extract-vocals
```

或者在 `.env` 文件中设置：

```
EXTRACT_VOCALS_DIR=/root/autodl-tmp/extract-vocals
```

## 处理流程

1. **用户上传音频**
   - 文件保存到 `UPLOAD_DIR` 目录
   - 转换为 WAV 格式（如果需要）

2. **用户创建角色**
   - 调用 `/api/characters` POST 接口
   - 如果提供了 `fileId`，系统会：
     - 获取音频文件路径（`init_input`）
     - 调用 `process_audio_with_deepfilternet_denoiser()` 处理音频
     - 生成处理后的音频文件（`*_clean.wav`）
     - 保存处理后的路径到 `clean_input` 字段

3. **处理结果**
   - `init_input`：原始音频文件路径
   - `clean_input`：处理后的音频文件路径（降噪+去混响）

## 数据库字段

### user_input_audio 表

- `init_input`：原始音频文件路径
- `clean_input`：处理后的音频文件路径（DeepFilterNet + Denoiser 处理）

## 错误处理

- 如果音频处理失败，`clean_input` 将为 `None`
- 错误信息会记录在日志中
- 处理失败不会影响角色创建流程

## 性能考虑

- 音频处理是同步进行的，可能会增加角色创建的响应时间
- 处理时间取决于音频长度和服务器性能
- 默认超时时间为 300 秒（5分钟）

## 未来优化建议

1. **异步处理**：将音频处理改为异步任务，使用 Celery 或类似工具
2. **队列系统**：使用消息队列处理音频处理任务
3. **进度反馈**：提供处理进度 API，让前端可以显示处理状态

## 测试

### 手动测试音频处理

```python
from scripts.audio_processor import process_audio_with_deepfilternet_denoiser

# 处理音频
result = process_audio_with_deepfilternet_denoiser(
    input_path="/path/to/input.wav",
    output_path="/path/to/output.wav"
)

if result:
    print(f"处理成功: {result}")
else:
    print("处理失败")
```

### 测试角色创建 API

```bash
# 1. 上传音频文件
curl -X POST http://localhost:8080/api/files/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@audio.wav"

# 2. 创建角色（会自动处理音频）
curl -X POST http://localhost:8080/api/characters \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试角色",
    "fileId": "1"
  }'
```

## 故障排除

### 问题：音频处理脚本找不到

**错误**：`音频处理脚本不存在: /root/autodl-tmp/extract-vocals/audio_processor_service.py`

**解决**：
1. 检查 `EXTRACT_VOCALS_DIR` 环境变量是否正确
2. 确认 extract-vocals 项目已正确部署
3. 确认 `audio_processor_service.py` 文件存在且有执行权限

### 问题：处理超时

**错误**：`音频处理超时（超过 300 秒）`

**解决**：
1. 检查音频文件是否过大
2. 检查服务器性能
3. 可以增加超时时间（修改 `audio_processor.py` 中的 `timeout` 参数）

### 问题：权限错误

**错误**：`Permission denied`

**解决**：
1. 确认 `audio_processor_service.py` 有执行权限：`chmod +x audio_processor_service.py`
2. 确认 Python 解释器路径正确

## 相关文件

- `/root/autodl-tmp/extract-vocals/audio_processor_service.py` - 音频处理服务
- `/root/autodl-tmp/extract-vocals/process_audio.py` - 核心处理脚本
- `tts-story/scripts/audio_processor.py` - 音频处理调用模块
- `tts-story/scripts/character_api.py` - 角色创建 API
- `tts-story/scripts/user_input_audio_dao.py` - 音频数据访问对象

