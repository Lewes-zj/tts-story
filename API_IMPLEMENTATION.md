# API接口实现说明

## 概述

本文档说明已实现的API接口，所有接口均按照 `API接口文档.md` 中的规范实现。

## 数据库准备

1. 执行基础表结构：
   ```bash
   mysql -u root -p story < db/story.sql
   ```

2. 执行补充表结构：
   ```bash
   mysql -u root -p story < db/story_supplement.sql
   ```

## 安装依赖

```bash
pip install -r requirements.txt
```

新增的依赖：
- `PyJWT>=2.8.0` - JWT token生成和验证
- `email-validator>=2.0.0` - 邮箱格式验证
- `bcrypt>=4.0.0` - 密码加密

## 启动服务

```bash
python scripts/main_api.py
```

或使用uvicorn：

```bash
uvicorn scripts.main_api:app --host 0.0.0.0 --port 8000
```

## 已实现的API接口

### 1. 用户管理接口

#### 1.1 用户注册
- **接口地址**: `POST /api/auth/register`
- **请求参数**: 
  ```json
  {
    "username": "string",
    "email": "string",
    "password": "string"
  }
  ```
- **响应数据**: 
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "id": "string",
      "username": "string",
      "email": "string",
      "createdAt": "timestamp"
    }
  }
  ```

#### 1.2 用户登录
- **接口地址**: `POST /api/auth/login`
- **请求参数**: 
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
- **响应数据**: 
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "user": {
        "id": "string",
        "username": "string",
        "email": "string"
      },
      "token": "string"
    }
  }
  ```

#### 1.3 用户退出
- **接口地址**: `POST /api/auth/logout`
- **请求头**: `Authorization: Bearer <token>`
- **响应数据**: 
  ```json
  {
    "code": 200,
    "message": "success",
    "data": null
  }
  ```

### 2. 角色管理接口

#### 2.1 创建角色
- **接口地址**: `POST /api/characters`
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: 
  ```json
  {
    "name": "string"  // 角色名称，2-6个字符
  }
  ```

#### 2.2 获取用户角色
- **接口地址**: `GET /api/characters`
- **请求头**: `Authorization: Bearer <token>`

### 3. 故事管理接口

#### 3.1 获取故事列表
- **接口地址**: `GET /api/stories`
- **请求参数**: 
  - `category`: string (可选，分类筛选)
  - `page`: int (可选，页码，默认1)
  - `size`: int (可选，每页数量，默认10)

#### 3.2 获取故事详情
- **接口地址**: `GET /api/stories/{id}`

### 4. 语音生成任务接口

#### 4.1 创建语音生成任务
- **接口地址**: `POST /api/tasks`
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: 
  ```json
  {
    "storyId": "string",
    "characterId": "string"
  }
  ```

#### 4.2 获取任务列表
- **接口地址**: `GET /api/tasks`
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: 
  - `status`: string (可选，状态筛选)
  - `page`: int (可选，页码，默认1)
  - `size`: int (可选，每页数量，默认10)

#### 4.3 获取任务详情
- **接口地址**: `GET /api/tasks/{id}`
- **请求头**: `Authorization: Bearer <token>`

#### 4.4 获取任务状态
- **接口地址**: `GET /api/tasks/{id}/status`
- **响应数据**: 
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "status": "string"  // generating, completed
    }
  }
  ```

### 5. 文件接口

#### 5.1 上传录音文件
- **接口地址**: `POST /api/files/upload`
- **请求头**: 
  - `Authorization: Bearer <token>`
  - `Content-Type: multipart/form-data`
- **请求参数**: 
  - `file`: File (录音文件)

#### 5.2 获取音频文件
- **接口地址**: `GET /api/files/audio/{id}`
- **响应**: 音频文件流

## 文件结构

```
scripts/
├── auth_api.py          # 用户认证API
├── character_api.py     # 角色管理API
├── story_api.py         # 故事管理API
├── task_api.py          # 任务管理API
├── file_api.py          # 文件管理API
├── jwt_util.py          # JWT工具类
├── user_dao.py          # 用户数据访问对象
├── character_dao.py     # 角色数据访问对象
├── story_dao.py         # 故事数据访问对象
├── task_dao.py          # 任务数据访问对象
├── file_dao.py          # 文件数据访问对象
└── main_api.py          # 主API应用（已整合所有路由）
```

## 配置说明

### 数据库配置
配置文件：`config/database.yaml`

```yaml
mysql:
  host: localhost
  port: 3306
  user: root
  password: root
  database: story
  charset: utf8mb4
```

### JWT配置
在 `scripts/jwt_util.py` 中配置：
- `JWT_SECRET`: JWT密钥（生产环境请修改）
- `JWT_EXPIRATION_HOURS`: Token过期时间（默认24小时）

### 文件上传配置
在 `scripts/file_api.py` 中配置：
- `UPLOAD_DIR`: 文件上传目录（默认：`/tmp/tts-story/uploads`）
- `FILE_URL_PREFIX`: 文件访问URL前缀

可通过环境变量设置：
```bash
export UPLOAD_DIR="/path/to/upload"
export FILE_URL_PREFIX="http://your-domain.com/api/files/audio/"
```

## 注意事项

1. **密码加密**: ✅ 已实现使用bcrypt加密存储密码
2. **JWT Secret**: 生产环境必须修改 `scripts/jwt_util.py` 中的 `JWT_SECRET`
3. **文件存储**: 确保文件上传目录有写入权限
4. **数据库连接**: 确保数据库配置正确，且已执行所有SQL脚本

## 故障排查

如果启动服务后在 `/docs` 看不到新的API接口，请检查：

1. **查看启动日志**：启动服务时应该看到以下信息：
   ```
   ✓ 新的API路由已成功注册
     - 认证API: /api/auth
     - 角色管理API: /api/characters
     - 故事管理API: /api/stories
     - 任务管理API: /api/tasks
     - 文件管理API: /api/files
   ```

2. **检查导入错误**：如果看到错误信息，请检查：
   - 所有依赖是否已安装：`pip install -r requirements.txt`
   - 数据库配置是否正确
   - 所有DAO文件是否存在

3. **查看路由列表**：启动服务时会自动打印所有已注册的路由，检查是否包含 `/api/` 开头的路由

4. **重启服务**：修改代码后需要重启服务才能生效

## API文档访问

启动服务后，可以通过以下地址访问API文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 测试示例

### 1. 用户注册
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "123456"
  }'
```

### 2. 用户登录
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "123456"
  }'
```

### 3. 创建角色（需要token）
```bash
curl -X POST "http://localhost:8000/api/characters" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "角色名"
  }'
```

### 4. 获取故事列表
```bash
curl "http://localhost:8000/api/stories?page=1&size=10"
```

### 5. 创建任务（需要token）
```bash
curl -X POST "http://localhost:8000/api/tasks" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "storyId": 1,
    "characterId": 1
  }'
```

## 错误码

- `200`: 请求成功
- `400`: 请求参数错误
- `401`: 未授权
- `403`: 禁止访问
- `404`: 资源不存在
- `500`: 服务器内部错误

