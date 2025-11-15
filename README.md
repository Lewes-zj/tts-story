# TTS情绪向量处理系统

## 简介

本系统基于IndexTTS技术，能够根据预定义的情绪向量配置生成不同情绪风格的语音文件。

## 功能特性

- 根据数据库中的情绪向量配置生成语音
- 支持生成两种不同类型的音频文件（SPK和EMO）
- 自动将生成结果存储到数据库
- 提供RESTful API接口
- 支持批量处理

## 系统架构

```
情绪向量配置表 (emo_vector_config)
        ↓
情绪向量处理器 (EmoVectorProcessor)
        ↓
TTS生成器 (generate_by_emo_vector)
        ↓
用户情绪音频表 (user_emo_audio)
```

## 数据库表结构

### emo_vector_config 表
存储情绪向量配置信息

```sql
CREATE TABLE `emo_vector_config`  (
  `id` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
  `type` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '情绪类型',
  `spk_emo_vector` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '高质量 input 音频情绪向量',
  `spk_emo_alpha` decimal(10, 2) NOT NULL COMMENT '高质量input音频情绪混合系数',
  `emo_vector` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '情绪引导音频情绪向量',
  `emo_alpha` decimal(10, 2) NOT NULL COMMENT '情绪引导音频情绪混合系数',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 11 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
```

### user_emo_audio 表
存储用户生成的情绪音频信息

```sql
CREATE TABLE `user_emo_audio`  (
  `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL COMMENT '用户ID',
  `role_id` bigint(20) NOT NULL COMMENT '角色ID',
  `emo_type` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '情绪类型',
  `spk_audio_prompt` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '高质量 input 音频',
  `spk_emo_vector` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '高质量 input 音频情绪向量',
  `spk_emo_alpha` decimal(10, 2) NOT NULL COMMENT '高质量input音频情绪混合系数',
  `emo_audio_prompt` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '情绪引导音频',
  `emo_vector` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '情绪引导音频情绪向量',
  `emo_alpha` decimal(10, 2) NOT NULL COMMENT '情绪引导音频情绪混合系数',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_uid_rid`(`user_id`, `role_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
```

## API接口

### 情绪向量处理接口

**POST** `/emo_vector/process_emo_vector/`

处理情绪向量，生成不同情绪的语音文件

#### 请求参数
```json
{
  "user_id": 1,
  "role_id": 1,
  "clean_input_audio": "/path/to/input/audio.wav",
  "text": "需要转换的文本内容"
}
```

#### 响应示例
```json
{
  "user_id": 1,
  "role_id": 1,
  "text": "需要转换的文本内容",
  "generated_files": [
    {
      "record_id": 1,
      "emo_type": "悲伤",
      "output_path": "/path/to/generated/audio.wav",
      "text": "需要转换的文本内容"
    }
  ]
}
```

## 使用方法

1. 启动服务：
   ```bash
   python scripts/start_all_services.py
   ```

2. 访问API文档：
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

3. 调用情绪向量处理接口生成语音文件

## 开发指南

### 核心组件

1. **[generate_by_emo_vector.py](file:///E:/xxx/python_project/tts/scripts/generate_by_emo_vector.py)** - TTS生成器，负责调用IndexTTS生成音频文件
2. **[emo_vector_processor.py](file:///E:/xxx/python_project/tts/scripts/emo_vector_processor.py)** - 情绪向量处理器，负责处理数据库配置并生成TTS参数
3. **[emo_vector_api.py](file:///E:/xxx/python_project/tts/scripts/emo_vector_api.py)** - RESTful API接口，提供HTTP服务
4. **[main_api.py](file:///E:/xxx/python_project/tts/scripts/main_api.py)** - 统一API网关，整合所有API服务

### 数据访问对象

1. **[emo_vector_config_dao.py](file:///E:/xxx/python_project/tts/scripts/emo_vector_config_dao.py)** - 情绪向量配置数据访问对象
2. **[user_emo_audio_dao.py](file:///E:/xxx/python_project/tts/scripts/user_emo_audio_dao.py)** - 用户情绪音频数据访问对象
3. **[base_dao.py](file:///E:/xxx/python_project/tts/scripts/base_dao.py)** - 基础数据访问对象

## 测试

可以使用以下脚本进行测试：

1. **[test_emo_vector_processor.py](file:///E:/xxx/python_project/tts/scripts/test_emo_vector_processor.py)** - 测试情绪向量处理器
2. **[test_emo_vector_api.py](file:///E:/xxx/python_project/tts/scripts/test_emo_vector_api.py)** - 测试情绪向量API