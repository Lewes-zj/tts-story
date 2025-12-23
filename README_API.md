# FastAPI 音频生成服务 - 快速开始指南

## 📦 安装

```bash
# 1. 安装 FastAPI 依赖
pip install -r requirements-api.txt

# 2. 确保已安装音频处理依赖
pip install -r requirements.txt
```

## 🚀 启动服务

```bash
# 开发模式 (自动重载)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 或者直接运行
python -m app.main
```

服务启动后访问:

- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## 📝 API 使用示例

### 1. 创建音频生成任务

```bash
curl -X POST "http://localhost:8000/api/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "input_wav": "/path/to/speaker_voice.wav",
    "json_db": "/path/to/dialogue_tasks.json",
    "emo_audio_folder": "/path/to/emotion_audios",
    "source_audio": "/path/to/original_audio.wav",
    "script_json": "/path/to/script.json",
    "bgm_path": "/path/to/background_music.wav",
    "task_name": "第一集生成"
  }'
```

**响应:**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "任务已创建，正在后台执行",
  "created_at": "2025-12-21T23:50:00"
}
```

### 2. 查询任务状态

```bash
curl "http://localhost:8000/api/task/550e8400-e29b-41d4-a716-446655440000"
```

**处理中响应:**

```json
{
  "task_id": "550e8400-...",
  "status": "processing",
  "progress": "Step 2/4: 正在去除静音...",
  "current_step": 2,
  "total_steps": 4,
  "steps": [
    {
      "step_number": 1,
      "step_name": "Voice Cloning",
      "status": "completed",
      "result": {
        "total": 50,
        "success": 50,
        "failed": 0
      }
    }
  ]
}
```

**完成后响应:**

```json
{
  "task_id": "550e8400-...",
  "status": "completed",
  "progress": "✅ 任务完成！所有步骤已成功执行",
  "current_step": 4,
  "total_steps": 4,
  "output_wav": "/path/to/data/tasks/550e8400-.../4_final_output.wav",
  "result": {
    "task_dir": "/path/to/data/tasks/550e8400-...",
    "output_wav": "/path/to/data/tasks/550e8400-.../4_final_output.wav"
  }
}
```

### 3. 列出所有任务

```bash
# 列出所有任务
curl "http://localhost:8000/api/tasks"

# 只看已完成的任务
curl "http://localhost:8000/api/tasks?status=completed"

# 限制返回数量
curl "http://localhost:8000/api/tasks?limit=5"
```

### 4. 删除任务

```bash
curl -X DELETE "http://localhost:8000/api/task/550e8400-e29b-41d4-a716-446655440000"
```

## 🎯 处理流程

每个任务会按顺序执行 4 个步骤:

```
Step 1: Voice Cloning (语音克隆) 🎤
  ↓ 输出: data/tasks/{task_id}/1_cloned/

Step 2: Trim Silence (去除静音) ✂️
  ↓ 输出: data/tasks/{task_id}/2_trimmed/

Step 3: Build Sequence (构建序列) 📊
  ↓ 输出: data/tasks/{task_id}/3_sequence.json

Step 4: Alignment (对齐合成) 🎵
  ↓ 输出: data/tasks/{task_id}/4_final_output.wav ✨
```

## 📂 文件结构

```
data/
└── tasks/
    ├── tasks.json                    # 任务持久化存储
    └── {task_id}/                    # 每个任务的独立目录
        ├── 1_cloned/                 # Step 1 输出
        ├── 2_trimmed/                # Step 2 输出
        ├── 3_sequence.json           # Step 3 输出
        └── 4_final_output.wav        # Step 4 最终输出
```

## ⚙️ 配置说明

### GPU 并发控制

系统默认限制**同时最多 1 个任务**执行 AI 推理(Voice Cloning 步骤)，防止 GPU 显存溢出。

如需调整，修改 `app/services/audio_pipeline.py`:

```python
# 改为允许2个任务同时执行
gpu_semaphore = threading.Semaphore(2)
```

### 线程池配置

默认线程池大小为 5。如需调整，修改 `app/main.py`:

```python
executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="audio_pipeline_")
```

## 🔍 监控与调试

### 查看日志

日志会同时输出到:

- 控制台
- `app.log` 文件

```bash
# 实时查看日志
tail -f app.log
```

### 任务状态持久化

所有任务状态保存在 `data/tasks.json`，服务重启后自动恢复。

## 🛠️ 常见问题

### 1. 任务一直是 pending 状态

检查日志是否有错误，可能是:

- 文件路径不存在
- 权限问题
- 依赖缺失

### 2. GPU 显存不足

- 确认同时只有 1 个任务在执行 (默认配置)
- 检查 `gpu_semaphore` 配置

### 3. 任务失败

查看任务详情中的 `error` 字段和各步骤的 `error` 信息

## 📚 Python SDK 示例

```python
import requests

# 创建任务
response = requests.post("http://localhost:8000/api/generate", json={
    "input_wav": "/path/to/speaker.wav",
    "json_db": "/path/to/tasks.json",
    "emo_audio_folder": "/path/to/emotions",
    "source_audio": "/path/to/source.wav",
    "script_json": "/path/to/script.json",
    "bgm_path": "/path/to/bgm.wav",
    "task_name": "测试任务"
})

task = response.json()
task_id = task["task_id"]
print(f"任务已创建: {task_id}")

# 轮询任务状态
import time
while True:
    status_response = requests.get(f"http://localhost:8000/api/task/{task_id}")
    status = status_response.json()

    print(f"状态: {status['status']} - {status['progress']}")

    if status["status"] in ["completed", "failed"]:
        break

    time.sleep(5)

if status["status"] == "completed":
    print(f"✅ 任务完成！输出文件: {status['output_wav']}")
else:
    print(f"❌ 任务失败: {status['error']}")
```

## 🎉 开始使用

1. 确保所有依赖已安装
2. 准备好必需的输入文件
3. 启动服务
4. 调用 API 创建任务
5. 查询任务状态，等待完成
6. 获取最终输出音频文件

祝您使用愉快！🚀
