"""
Pydantic 数据模型定义

定义API请求和响应的数据模型
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerateAudioRequest(BaseModel):
    """音频生成请求模型"""

    # Step 1: Voice Cloning 参数
    input_wav: str = Field(..., description="音色参考音频路径")
    json_db: str = Field(..., description="JSON配置文件路径 (包含任务列表)")
    emo_audio_folder: Optional[str] = Field(None, description="情感音频文件夹路径")

    # Step 2: Trim Silence 参数 (可选，使用默认值)
    silence_thresh: int = Field(-40, description="静音阈值 (dBFS)")

    # Step 3: Build Sequence 参数
    source_audio: str = Field(..., description="源音频文件路径 (用于对齐)")
    script_json: str = Field(..., description="脚本JSON文件路径")

    # Step 4: Alignment 参数
    bgm_path: str = Field(..., description="BGM音频文件路径")

    # 可选参数
    task_name: Optional[str] = Field(None, description="任务名称")

    class Config:
        json_schema_extra = {
            "example": {
                "input_wav": "/path/to/speaker.wav",
                "json_db": "/path/to/tasks.json",
                "emo_audio_folder": "/path/to/emotions",
                "source_audio": "/path/to/source.wav",
                "script_json": "/path/to/script.json",
                "bgm_path": "/path/to/bgm.wav",
                "task_name": "Episode 1 Generation",
            }
        }


class TaskResponse(BaseModel):
    """任务创建响应模型"""

    task_id: str = Field(..., description="任务唯一标识符")
    status: TaskStatus = Field(..., description="任务状态")
    message: str = Field(..., description="响应消息")
    created_at: datetime = Field(..., description="任务创建时间")


class StepProgress(BaseModel):
    """步骤进度模型"""

    step_number: int = Field(..., description="步骤编号")
    step_name: str = Field(..., description="步骤名称")
    status: TaskStatus = Field(..., description="步骤状态")
    result: Optional[Dict[str, Any]] = Field(None, description="步骤执行结果")
    error: Optional[str] = Field(None, description="错误信息")


class TaskStatusResponse(BaseModel):
    """任务状态查询响应模型"""

    task_id: str = Field(..., description="任务ID")
    task_name: Optional[str] = Field(None, description="任务名称")
    status: TaskStatus = Field(..., description="当前状态")
    progress: str = Field(..., description="进度描述")
    current_step: int = Field(..., description="当前步骤编号")
    total_steps: int = Field(4, description="总步骤数")
    steps: List[StepProgress] = Field(default_factory=list, description="各步骤详情")

    # 最终结果
    result: Optional[Dict[str, Any]] = Field(None, description="最终结果")
    output_wav: Optional[str] = Field(None, description="最终输出音频文件路径")
    output_url: Optional[str] = Field(None, description="最终输出音频可访问URL")

    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    # 错误信息
    error: Optional[str] = Field(None, description="错误信息 (如果失败)")


class TaskListResponse(BaseModel):
    """任务列表响应模型"""

    total: int = Field(..., description="任务总数")
    tasks: List[TaskStatusResponse] = Field(..., description="任务列表")


class GenerateByIdsRequest(BaseModel):
    """基于ID的音频生成请求模型"""

    story_id: int = Field(..., description="故事ID")
    user_id: int = Field(..., description="用户ID")
    role_id: int = Field(..., description="角色ID (角色/声音ID)")
    task_name: Optional[str] = Field(None, description="任务名称 (可选)")

    class Config:
        json_schema_extra = {
            "example": {
                "story_id": 1,
                "user_id": 101,
                "role_id": 5,
                "task_name": "第一集生成",
            }
        }
