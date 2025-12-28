# 音频 URL 配置说明

## 问题背景

音频文件生成后存放在 `tts-story/data/tasks/{task_id}/` 目录中，但只有 `story-web` 前端项目对外暴露（通过算力云域名访问）。为了让前端能够播放音频，需要配置音频文件的访问路径。

## 解决方案

### 1. 后端静态文件服务

后端 FastAPI 已经挂载了两个静态文件服务：

**1. `/media` 挂载点**（任务输出目录）：

```python
app.mount(
    "/media",
    StaticFiles(directory="data/tasks", check_dir=False),
    name="media",
)
```

这样，音频文件可以通过 `/media/{task_id}/4_final_output.wav` 访问。

**2. `/outputs` 挂载点**（outputs 目录）：

```python
# 获取项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
outputs_dir = os.path.join(project_root, "outputs")
os.makedirs(outputs_dir, exist_ok=True)

app.mount(
    "/outputs",
    StaticFiles(directory=outputs_dir, check_dir=False),
    name="outputs",
)
```

这样，outputs 目录中的文件可以通过以下方式访问：

- 根目录文件：`/outputs/{filename}` （例如：`/outputs/1766503007987_clean.wav`）
- 子目录文件：`/outputs/{user_id}/{role_id}/{filename}` （例如：`/outputs/22/31/1766503007987_clean.wav`）

**注意**：使用绝对路径可以确保 FastAPI 正确解析子目录路径，避免相对路径解析问题。

### 2. 前端代理配置

前端 Vite 配置中已经添加了 `/media` 和 `/outputs` 的代理，将请求转发到后端：

```javascript
'/media': {
  target: 'http://localhost:8000',
  changeOrigin: true,
  secure: false
},
'/outputs': {
  target: 'http://localhost:8000',
  changeOrigin: true,
  secure: false
}
```

### 3. PUBLIC_BASE_URL 环境变量设置

`PUBLIC_BASE_URL` 用于生成音频的完整访问 URL。有两种设置方式：

#### 方式一：使用相对路径（推荐，适用于前端代理场景）

**不设置 `PUBLIC_BASE_URL`**，或者设置为空字符串：

```bash
# 不设置环境变量，或设置为空
export PUBLIC_BASE_URL=""
```

后端会返回相对路径：`/media/{task_id}/4_final_output.wav`

前端可以直接使用这个相对路径，因为 Vite 代理会自动转发到后端。

#### 方式二：使用绝对路径（适用于直接访问后端）

如果算力云域名直接指向后端服务，可以设置完整的域名：

```bash
# 设置算力云给的域名（例如：https://xxx-6008.gradio.live）
export PUBLIC_BASE_URL="https://xxx-6008.gradio.live"
```

后端会返回绝对路径：`https://xxx-6008.gradio.live/media/{task_id}/4_final_output.wav`

## 配置步骤

### 对于你的场景（前端在 6008 端口，通过算力云域名访问）

**推荐配置：不设置 `PUBLIC_BASE_URL`，使用相对路径**

1. **确保后端服务运行在 8000 端口**：

   ```bash
   cd tts-story
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **确保前端 Vite 配置了 `/media` 和 `/outputs` 代理**（已完成）：

   - 前端在 6008 端口启动
   - Vite 自动将 `/media` 和 `/outputs` 请求代理到 `http://localhost:8000`

3. **后端不需要设置 `PUBLIC_BASE_URL`**：
   - 后端会返回相对路径 `/media/{task_id}/4_final_output.wav`
   - 前端通过代理访问，路径会自动转发到后端

### 验证配置

1. 启动后端服务（8000 端口）
2. 启动前端服务（6008 端口）
3. 创建一个生成任务
4. 任务完成后，检查任务状态中的 `output_url` 字段
5. 前端应该能够通过 `output_url` 播放音频

## 工作流程

```
用户访问算力云域名 (例如: https://xxx-6008.gradio.live)
    ↓
前端 Vite 服务 (6008端口)
    ↓
前端请求 /media/{task_id}/4_final_output.wav
    ↓
Vite 代理转发到 http://localhost:8000/media/{task_id}/4_final_output.wav
    ↓
后端 FastAPI 返回音频文件
    ↓
前端播放音频
```

## 注意事项

1. **确保后端服务运行**：前端代理需要后端服务在 8000 端口运行
2. **文件权限**：确保 `data/tasks/` 和 `outputs/` 目录有读取权限
3. **CORS 配置**：后端已经配置了 CORS，允许跨域访问
4. **相对路径 vs 绝对路径**：
   - 使用相对路径：前端代理自动处理，无需额外配置
   - 使用绝对路径：需要确保域名正确，且后端可以直接访问

## 故障排查

### 问题：前端无法播放音频

1. **检查后端服务是否运行**：

   ```bash
   curl http://localhost:8000/health
   ```

2. **检查音频文件是否存在**：

   ```bash
   ls -la tts-story/data/tasks/{task_id}/4_final_output.wav
   ```

3. **检查前端代理配置**：

   - 确认 `vite.config.js` 中有 `/media` 和 `/outputs` 代理配置
   - 重启前端服务

4. **检查浏览器网络请求**：
   - 打开浏览器开发者工具
   - 查看 Network 标签
   - 检查 `/media/...` 和 `/outputs/...` 请求是否成功

### 问题：返回 404 错误

- 检查任务 ID 是否正确
- 检查音频文件是否已生成完成
- 检查文件路径是否正确

### 问题：CORS 错误

- 后端已经配置了 CORS，允许所有来源
- 如果仍有问题，检查后端日志

### 问题：子目录文件无法访问（例如 `/outputs/22/31/filename.wav`）

1. **检查文件是否存在**：

   ```bash
   ls -la tts-story/outputs/22/31/filename.wav
   ```

2. **检查目录权限**：

   ```bash
   ls -ld tts-story/outputs/22/31/
   ```

   确保目录有读取权限

3. **检查后端配置**：

   - 确认 `app/main.py` 中使用的是绝对路径配置
   - 确认 `StaticFiles` 的 `directory` 参数是绝对路径
   - 重启后端服务

4. **验证访问路径**：

   - 确保访问路径以 `/outputs/` 开头（带前导斜杠）
   - 例如：`/outputs/22/31/1766503007987_clean.wav` ✅
   - 错误：`outputs/22/31/1766503007987_clean.wav` ❌（缺少前导斜杠）

5. **测试直接访问**：
   ```bash
   curl http://localhost:8000/outputs/22/31/1766503007987_clean.wav
   ```

### 问题：处理流程中文件无法通过 URL 访问（文件系统同步延迟）

**症状**：

- 音频处理流程中，步骤 1 完成后生成的音频文件，在步骤 2 通过 HTTP URL 访问时失败
- 但整个流程完成后，文件可以正常访问
- 错误信息：`ResponseTimeout` 或 `404 Not Found`

**原因**：

1. 文件系统同步延迟：文件写入后，文件系统可能还没有完全同步到磁盘
2. 文件权限问题：新创建的文件可能权限不正确
3. FastAPI StaticFiles 缓存：可能缓存了目录结构，新文件未被识别

**解决方案**（已在代码中实现）：

1. **文件同步和验证**：

   - 在 `character_api.py` 中添加了 `ensure_file_accessible()` 函数
   - 确保文件权限正确（可读）
   - 刷新文件系统缓存
   - 验证文件可读性

2. **处理流程优化**：

   - 步骤 1 完成后，立即验证文件可访问性
   - 步骤 2 使用 URL 前，再次验证文件并添加短暂延迟（0.5 秒）
   - 验证文件大小，确保文件已完全写入

3. **重试机制**：
   - 如果文件验证失败，会重试最多 5 次
   - 每次重试间隔 0.5 秒

**代码位置**：

- `tts-story/scripts/character_api.py` 中的 `ensure_file_accessible()` 函数
- 在步骤 1 完成后和步骤 2 使用 URL 前调用

**如果问题仍然存在**：

1. **检查文件系统类型**：

   ```bash
   df -T /root/autodl-tmp/tts-story/outputs
   ```

   某些网络文件系统（如 NFS）可能有更长的同步延迟

2. **增加延迟时间**：
   修改 `character_api.py` 中的延迟时间：

   ```python
   time.sleep(1.0)  # 增加到1秒或更长
   ```

3. **检查文件权限**：

   ```bash
   ls -la /root/autodl-tmp/tts-story/outputs/2/57/
   ```

   确保文件有读取权限（`-r--r--r--` 或 `-rw-r--r--`）

4. **使用本地文件路径**（如果 CosyVoice 支持）：
   如果 CosyVoice V3 API 支持本地文件路径，可以考虑直接传递文件路径而不是 URL
