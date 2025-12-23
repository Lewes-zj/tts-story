# 后端音频访问配置检查清单

## 概述

为了让前端能够访问生成的音频文件，后端需要正确配置和运行。本文档列出了所有需要检查的配置项。

## ✅ 必需配置

### 1. 后端服务运行在 8000 端口

后端 FastAPI 服务必须运行在 **8000 端口**，因为前端 Vite 代理配置指向 `http://localhost:8000`。

**启动方式**：

```bash
cd tts-story
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

或者直接运行：

```bash
cd tts-story
python -m app.main
```

**验证服务是否运行**：

```bash
# 检查 8000 端口是否被占用
lsof -i :8000

# 或者测试健康检查接口
curl http://localhost:8000/health
```

应该返回：`{"status": "healthy", "message": "Service is running"}`

### 2. 静态文件目录存在

确保 `data/tasks` 目录存在，这是音频文件的存储位置。

**检查目录**：

```bash
cd tts-story
ls -la data/tasks/
```

如果目录不存在，会自动创建（在生成任务时），但建议提前创建：

```bash
mkdir -p data/tasks
```

### 3. 文件权限正确

确保 `data/tasks` 目录有读取权限，生成的音频文件有读取权限。

**设置权限**（如果需要）：

```bash
chmod -R 755 data/tasks
```

### 4. 静态文件挂载配置

后端已经配置了静态文件挂载（在 `app/main.py` 中）：

```python
app.mount(
    "/media",
    StaticFiles(directory="data/tasks", check_dir=False),
    name="media",
)
```

**验证静态文件服务**：

生成一个测试任务后，尝试访问：

```bash
# 假设任务ID是 abc123
curl http://localhost:8000/media/abc123/4_final_output.wav
```

如果返回音频文件内容（二进制数据），说明配置正确。

### 5. 前端代理配置

前端 Vite 配置（`story-web/vite.config.js`）已经配置了 `/media` 代理：

```javascript
'/media': {
  target: 'http://localhost:8000',
  changeOrigin: true,
  secure: false
}
```

**验证前端代理**：

1. 启动前端服务（6008端口）
2. 在浏览器中访问：`http://localhost:6008/media/{task_id}/4_final_output.wav`
3. 应该能够下载或播放音频文件

## 🔍 完整检查流程

### 步骤 1: 检查后端服务

```bash
# 1. 检查后端是否运行
curl http://localhost:8000/health

# 2. 检查后端API根路径
curl http://localhost:8000/
```

### 步骤 2: 检查目录结构

```bash
cd tts-story

# 检查目录是否存在
ls -la data/tasks/

# 如果不存在，创建目录
mkdir -p data/tasks
```

### 步骤 3: 测试音频访问

生成一个测试任务后：

```bash
# 获取任务ID（从任务状态响应中）
TASK_ID="your-task-id"

# 测试后端直接访问
curl -I http://localhost:8000/media/${TASK_ID}/4_final_output.wav

# 应该返回 200 OK
```

### 步骤 4: 测试前端代理

```bash
# 启动前端服务
cd story-web
npm run dev

# 在浏览器中访问（替换 TASK_ID）
http://localhost:6008/media/{TASK_ID}/4_final_output.wav
```

## 🚀 启动脚本示例

创建一个启动脚本 `start_backend.sh`：

```bash
#!/bin/bash

cd "$(dirname "$0")"

echo "=== 启动后端服务 ==="

# 检查 Python 环境
if ! command -v python &> /dev/null; then
    echo "❌ Python 未安装"
    exit 1
fi

# 检查依赖
if ! python -c "import fastapi" &> /dev/null; then
    echo "❌ FastAPI 未安装，请先安装依赖：pip install -r requirements.txt"
    exit 1
fi

# 创建必要的目录
mkdir -p data/tasks
mkdir -p data

# 启动服务
echo "🚀 启动 FastAPI 服务 (端口 8000)..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

使用方式：

```bash
chmod +x start_backend.sh
./start_backend.sh
```

## ⚠️ 常见问题

### 问题 1: 后端服务无法启动

**可能原因**：
- 8000 端口被占用
- 缺少依赖包

**解决方法**：

```bash
# 检查端口占用
lsof -i :8000

# 如果被占用，停止占用进程或更换端口
# 安装依赖
pip install -r requirements.txt
```

### 问题 2: 音频文件 404 错误

**可能原因**：
- 任务ID不正确
- 音频文件还未生成完成
- 文件路径错误

**解决方法**：

```bash
# 检查任务目录
ls -la data/tasks/{task_id}/

# 检查文件是否存在
ls -la data/tasks/{task_id}/4_final_output.wav
```

### 问题 3: 前端无法访问音频

**可能原因**：
- 后端服务未运行
- 前端代理配置错误
- CORS 问题

**解决方法**：

1. 确认后端服务运行：`curl http://localhost:8000/health`
2. 检查前端 Vite 配置中的代理设置
3. 检查浏览器控制台的网络请求错误

### 问题 4: 权限错误

**可能原因**：
- 文件权限不足
- 目录权限不足

**解决方法**：

```bash
# 设置目录权限
chmod -R 755 data/tasks

# 设置文件权限（生成后）
chmod 644 data/tasks/*/4_final_output.wav
```

## 📝 总结

**必需的操作**：

1. ✅ 确保后端服务运行在 **8000 端口**
2. ✅ 确保 `data/tasks` 目录存在
3. ✅ 确保文件有读取权限
4. ✅ 后端静态文件挂载已配置（代码中已完成）
5. ✅ 前端代理已配置（代码中已完成）

**无需额外操作**：
- ❌ 不需要设置 `PUBLIC_BASE_URL`（使用相对路径即可）
- ❌ 不需要配置 Nginx（前端 Vite 已处理代理）
- ❌ 不需要修改文件路径（使用默认路径即可）

**验证清单**：

- [ ] 后端服务运行在 8000 端口
- [ ] `data/tasks` 目录存在
- [ ] 可以访问 `http://localhost:8000/health`
- [ ] 可以访问 `http://localhost:8000/media/{task_id}/4_final_output.wav`
- [ ] 前端可以播放音频

完成以上检查后，音频文件应该可以正常访问了！

