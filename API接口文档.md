# 故事语音生成应用 - Java服务端接口文档

## 1. 概述
本文档定义了故事语音生成应用的Java服务端API接口，包括用户管理、角色管理、故事管理、语音生成任务等核心功能。

## 2. 技术规范
- 接口协议：HTTP/HTTPS
- 数据格式：JSON
- 字符编码：UTF-8
- 认证方式：JWT Token

## 3. 基础响应格式
```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

## 4. 用户管理接口

### 4.1 用户注册
**接口地址**: `POST /api/auth/register`  
**请求参数**:
```json
{
  "username": "string",
  "email": "string",
  "password": "string"
}
```
**响应数据**:
```json
{
  "id": "string",
  "username": "string",
  "email": "string",
  "createdAt": "timestamp"
}
```

### 4.2 用户登录
**接口地址**: `POST /api/auth/login`  
**请求参数**:
```json
{
  "username": "string",
  "password": "string"
}
```
**响应数据**:
```json
{
  "user": {
    "id": "string",
    "username": "string",
    "email": "string"
  },
  "token": "string"
}
```

### 4.3 用户退出
**接口地址**: `POST /api/auth/logout`  
**请求头**: `Authorization: Bearer <token>`  
**响应数据**: 无

## 5. 角色管理接口

### 5.1 创建角色
**接口地址**: `POST /api/characters`  
**请求头**: `Authorization: Bearer <token>`  
**请求参数**:
```json
{
  "name": "string" // 角色名称，2-6个字符
}
```
**响应数据**:
```json
{
  "id": "string",
  "name": "string",
  "createdAt": "timestamp"
}
```

### 5.2 获取用户角色
**接口地址**: `GET /api/characters`  
**请求头**: `Authorization: Bearer <token>`  
**响应数据**:
```json
{
  "id": "string",
  "name": "string",
  "createdAt": "timestamp"
}
```

## 6. 故事管理接口

### 6.1 获取故事列表
**接口地址**: `GET /api/stories`  
**请求参数**:
- category: string (可选，分类筛选)
- page: int (可选，页码，默认1)
- size: int (可选，每页数量，默认10)
**响应数据**:
```json
{
  "stories": [
    {
      "id": "string",
      "title": "string",
      "category": "string",
      "duration": "string",
      "coverUrl": "string"
    }
  ],
  "total": "int",
  "page": "int",
  "size": "int"
}
```

### 6.2 获取故事详情
**接口地址**: `GET /api/stories/{id}`  
**响应数据**:
```json
{
  "id": "string",
  "title": "string",
  "category": "string",
  "duration": "string",
  "coverUrl": "string",
  "content": "string" // 故事内容
}
```

## 7. 语音生成任务接口

### 7.1 创建语音生成任务
**接口地址**: `POST /api/tasks`  
**请求头**: `Authorization: Bearer <token>`  
**请求参数**:
```json
{
  "storyId": "string",
  "characterId": "string"
}
```
**响应数据**:
```json
{
  "id": "string",
  "storyId": "string",
  "characterId": "string",
  "status": "string", // generating, completed
  "createdAt": "timestamp"
}
```

### 7.2 获取任务列表
**接口地址**: `GET /api/tasks`  
**请求头**: `Authorization: Bearer <token>`  
**请求参数**:
- status: string (可选，状态筛选)
- page: int (可选，页码，默认1)
- size: int (可选，每页数量，默认10)
**响应数据**:
```json
{
  "tasks": [
    {
      "id": "string",
      "storyId": "string",
      "characterId": "string",
      "status": "string",
      "createdAt": "timestamp",
      "audioUrl": "string" // 仅在completed状态时返回
    }
  ],
  "total": "int",
  "page": "int",
  "size": "int"
}
```

### 7.3 获取任务详情
**接口地址**: `GET /api/tasks/{id}`  
**请求头**: `Authorization: Bearer <token>`  
**响应数据**:
```json
{
  "id": "string",
  "storyId": "string",
  "characterId": "string",
  "status": "string",
  "createdAt": "timestamp",
  "audioUrl": "string" // 仅在completed状态时返回
}
```

### 7.4 获取任务状态
**接口地址**: `GET /api/tasks/{id}/status`  
**响应数据**:
```json
{
  "status": "string" // generating, completed
}
```

## 8. 文件接口

### 8.1 上传录音文件
**接口地址**: `POST /api/files/upload`  
**请求头**: 
- `Authorization: Bearer <token>`
- `Content-Type: multipart/form-data`
**请求参数**:
- file: File (录音文件)
**响应数据**:
```json
{
  "id": "string",
  "url": "string",
  "name": "string"
}
```

### 8.2 获取音频文件
**接口地址**: `GET /api/files/audio/{id}`  
**响应**: 音频文件流

## 9. 错误码定义
| 错误码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 403 | 禁止访问 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 10. 数据模型

### 10.1 User (用户)
```json
{
  "id": "string",
  "username": "string",
  "email": "string",
  "createdAt": "timestamp"
}
```

### 10.2 Character (角色)
```json
{
  "id": "string",
  "name": "string",
  "createdAt": "timestamp"
}
```

### 10.3 Story (故事)
```json
{
  "id": "string",
  "title": "string",
  "category": "string",
  "duration": "string",
  "coverUrl": "string",
  "content": "string"
}
```

### 10.4 Task (任务)
```json
{
  "id": "string",
  "storyId": "string",
  "characterId": "string",
  "status": "string",
  "createdAt": "timestamp",
  "audioUrl": "string"
}
```