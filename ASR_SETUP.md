# 阿里云ASR语音识别配置指南

## 概述

本项目已集成阿里云ASR（自动语音识别）服务，用于验证用户录音内容是否与期望文本一致。

## 配置步骤

### 1. 开通阿里云智能语音交互服务

1. 登录[阿里云控制台](https://www.aliyun.com/)
2. 进入[智能语音交互产品页面](https://ai.aliyun.com/nls/trans)
3. 点击"开通并购买"，选择适合的服务类型
4. 阅读并同意服务协议，点击"立即开通"

### 2. 创建项目并获取AppKey

1. 进入[智能语音交互控制台](https://nls.console.aliyun.com/)
2. 创建一个新项目
3. 创建项目后，记录下**AppKey**（这是调用ASR服务所必需的）

### 3. 获取AccessKey

1. 登录[RAM访问控制控制台](https://ram.console.aliyun.com/)
2. 为您的阿里云账号或RAM用户创建AccessKey
3. 记录下**AccessKey ID**和**AccessKey Secret**

### 4. 配置阿里云密钥

1. 复制示例配置文件：
   ```bash
   cp config/aliyun_asr.yaml.example config/aliyun_asr.yaml
   ```

2. 编辑配置文件 `config/aliyun_asr.yaml`，填入实际的密钥信息：

   ```yaml
   # 阿里云ASR语音识别配置文件
   aliyun_asr:
     # 阿里云AccessKey ID
     access_key_id: "your_access_key_id"
     # 阿里云AccessKey Secret
     access_key_secret: "your_access_key_secret"
     # 阿里云ASR AppKey
     app_key: "your_app_key"
     # ASR服务端点（可选，默认使用上海区域）
     endpoint: "https://nls-gateway.cn-shanghai.aliyuncs.com"
   ```

   将 `your_access_key_id`、`your_access_key_secret` 和 `your_app_key` 替换为实际的密钥值。

**注意**: `config/aliyun_asr.yaml` 文件包含敏感信息，已被添加到 `.gitignore` 中，不会被提交到代码仓库。

### 5. 验证配置

启动后端服务后，访问健康检查接口：

```bash
curl http://localhost:8000/api/asr/health
```

如果配置正确，应该返回：

```json
{
  "status": "ok",
  "configured": true,
  "message": "ASR服务已配置"
}
```

## API接口说明

### 1. 识别上传的音频文件

**接口**: `POST /api/asr/recognize`

**请求**:
- Content-Type: `multipart/form-data`
- 参数:
  - `file`: 音频文件（支持 wav, mp3, webm 等格式）
  - `expected_text`: 期望的文本（可选，用于验证）

**响应**:
```json
{
  "recognizedText": "识别出的文本",
  "confidence": 0.95,
  "validationPassed": true,
  "message": "识别成功"
}
```

### 2. 通过文件ID识别音频

**接口**: `POST /api/asr/recognize-by-file-id`

**请求**:
```json
{
  "fileId": "文件ID",
  "expectedText": "期望的文本（可选）"
}
```

**响应**: 同上

### 3. 健康检查

**接口**: `GET /api/asr/health`

**响应**:
```json
{
  "status": "ok",
  "configured": true,
  "message": "ASR服务已配置"
}
```

## 前端使用

前端已集成ASR API调用，在 `RecordingPage.vue` 组件中：

1. 用户录音后，自动调用ASR API进行识别
2. 将识别结果与期望文本进行对比
3. 显示验证结果（通过/不通过）

## 注意事项

1. **Token获取**: 后端会自动获取阿里云Token，Token有效期为24小时，会自动刷新
2. **音频格式**: 支持 wav, mp3, webm 等格式，后端会自动转换为wav格式（如果安装了pydub和ffmpeg）
3. **费用**: 阿里云ASR服务按调用次数计费，请关注使用量和费用
4. **安全性**: AccessKey和Secret请妥善保管，不要提交到代码仓库

## 故障排查

### 问题1: ASR服务未配置

**错误信息**: "ASR服务未配置，请在 config/aliyun_asr.yaml 中配置"

**解决方法**: 
- 检查 `config/aliyun_asr.yaml` 文件是否存在
- 检查配置文件中的密钥是否正确填写
- 确保配置文件格式正确（YAML格式）
- 重启后端服务

### 问题2: Token获取失败

**错误信息**: "获取Token失败"

**解决方法**: 
- 检查AccessKey ID和Secret是否正确
- 检查网络连接是否正常
- 检查阿里云服务是否已开通

### 问题3: 识别失败

**错误信息**: "ASR请求失败"

**解决方法**:
- 检查AppKey是否正确
- 检查音频文件格式是否支持
- 检查音频文件大小是否在限制范围内
- 查看后端日志获取详细错误信息

## 相关文档

- [阿里云智能语音交互文档](https://help.aliyun.com/product/84413.html)
- [FunASR录音文件识别RESTful API](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-restful-api)

