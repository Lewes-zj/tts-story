"""
任务管理器 (Task Manager)

单例模式的任务管理器，负责：
1. 管理任务状态 (内存字典 + 持久化到 tasks.json)
2. 线程安全的状态更新
3. 服务启动时从 tasks.json 恢复历史任务
"""

import json
import os
import threading
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import logging

from app.models import TaskStatus, StepProgress, TaskStatusResponse

logger = logging.getLogger(__name__)


class TaskManager:
    """
    单例任务管理器

    特性:
    - 单例模式 (保证全局只有一个实例)
    - 线程安全 (使用 threading.Lock)
    - 持久化 (每次状态变更写入 tasks.json)
    """

    _instance = None
    _lock = threading.Lock()  # 类级别的锁，用于单例创建

    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化任务管理器"""
        # 防止重复初始化
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self.tasks: Dict[str, dict] = {}
        self._task_lock = threading.Lock()  # 实例级别的锁，用于任务操作

        # 持久化文件路径
        self.persistence_file = Path("data/tasks.json")
        self.persistence_file.parent.mkdir(parents=True, exist_ok=True)

        # 从文件加载历史任务
        self._load_from_file()

        logger.info("✅ TaskManager 初始化完成")

    def _load_from_file(self):
        """从 tasks.json 加载历史任务，并清理过期任务"""
        if not self.persistence_file.exists():
            logger.info("📂 未找到历史任务文件，从空状态开始")
            return

        try:
            with open(self.persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tasks = data
                logger.info(f"✅ 已加载 {len(self.tasks)} 个历史任务")
                
                # 启动时清理过期的失败任务（启动时还没有其他线程，不需要锁）
                cleaned_count = self._cleanup_expired_tasks(require_lock=False)
                if cleaned_count > 0:
                    logger.info(f"🧹 启动时清理了 {cleaned_count} 个过期任务")
        except Exception as e:
            logger.error(f"❌ 加载历史任务失败: {e}")
            self.tasks = {}

    def _save_to_file(self):
        """
        将当前任务状态保存到 tasks.json

        注意: 调用此方法前应该已经持有 _task_lock
        """
        try:
            # 确保目录存在
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)

            # 写入临时文件，然后原子性重命名 (防止写入过程中断导致文件损坏)
            temp_file = self.persistence_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, ensure_ascii=False, indent=2, default=str)

            # 原子性替换
            temp_file.replace(self.persistence_file)

        except Exception as e:
            logger.error(f"❌ 保存任务状态失败: {e}")

    def create_task(
        self, task_id: str, task_name: Optional[str] = None, total_steps: int = 4
    ) -> dict:
        """
        创建新任务

        Args:
            task_id: 任务唯一标识符
            task_name: 任务名称
            total_steps: 总步骤数

        Returns:
            创建的任务对象
        """
        with self._task_lock:
            now = datetime.now()

            task = {
                "task_id": task_id,
                "task_name": task_name,
                "status": TaskStatus.PENDING,
                "progress": "任务已创建，等待执行",
                "current_step": 0,
                "total_steps": total_steps,
                "steps": [],
                "result": None,
                "output_wav": None,
                "output_url": None,
                "error": None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "completed_at": None,
            }

            self.tasks[task_id] = task
            self._save_to_file()

            logger.info(f"✅ 任务已创建: {task_id}")
            return task

    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[str] = None,
        current_step: Optional[int] = None,
        result: Optional[dict] = None,
        output_wav: Optional[str] = None,
        output_url: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """
        更新任务状态 (线程安全)

        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度描述
            current_step: 当前步骤编号
            result: 执行结果
            output_wav: 输出文件路径
            error: 错误信息
        """
        with self._task_lock:
            if task_id not in self.tasks:
                logger.warning(f"⚠️ 任务不存在: {task_id}")
                return

            task = self.tasks[task_id]

            # 更新字段
            if status is not None:
                task["status"] = status
            if progress is not None:
                task["progress"] = progress
            if current_step is not None:
                task["current_step"] = current_step
            if result is not None:
                task["result"] = result
            if output_wav is not None:
                task["output_wav"] = output_wav
            if output_url is not None:
                task["output_url"] = output_url
            if error is not None:
                task["error"] = error

            # 更新时间戳
            task["updated_at"] = datetime.now().isoformat()

            # 如果任务完成或失败，记录完成时间
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task["completed_at"] = datetime.now().isoformat()

            # 持久化
            self._save_to_file()

            logger.info(f"📝 任务已更新: {task_id} - {status} - {progress}")

    def add_step_result(
        self,
        task_id: str,
        step_number: int,
        step_name: str,
        status: TaskStatus,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ):
        """
        添加步骤执行结果

        Args:
            task_id: 任务ID
            step_number: 步骤编号
            step_name: 步骤名称
            status: 步骤状态
            result: 步骤结果
            error: 错误信息
        """
        with self._task_lock:
            if task_id not in self.tasks:
                return

            task = self.tasks[task_id]

            step_data = {
                "step_number": step_number,
                "step_name": step_name,
                "status": status,
                "result": result,
                "error": error,
            }

            # 查找是否已存在该步骤，存在则更新，不存在则添加
            existing_step_index = next(
                (
                    i
                    for i, s in enumerate(task["steps"])
                    if s["step_number"] == step_number
                ),
                None,
            )

            if existing_step_index is not None:
                task["steps"][existing_step_index] = step_data
            else:
                task["steps"].append(step_data)

            # 持久化
            self._save_to_file()

    def _cleanup_expired_tasks(self, require_lock: bool = True) -> int:
        """
        清理过期的失败任务（计划删除时间已过）
        
        注意: 如果 require_lock=True，方法内部会获取锁。如果调用者已经持有锁，应设置 require_lock=False

        Args:
            require_lock: 是否需要在方法内部获取锁，默认 True

        Returns:
            清理的任务数量
        """
        def _do_cleanup():
            now = datetime.now()
            expired_task_ids = []
            
            for task_id, task in self.tasks.items():
                scheduled_delete_at = task.get("scheduled_delete_at")
                if scheduled_delete_at:
                    try:
                        delete_time = datetime.fromisoformat(scheduled_delete_at)
                        if delete_time <= now:
                            expired_task_ids.append(task_id)
                    except (ValueError, TypeError):
                        # 如果时间格式错误，跳过
                        continue
            
            # 删除过期任务
            for task_id in expired_task_ids:
                del self.tasks[task_id]
            
            if expired_task_ids:
                self._save_to_file()
            
            return len(expired_task_ids)
        
        if require_lock:
            with self._task_lock:
                return _do_cleanup()
        else:
            # 调用者已经持有锁
            return _do_cleanup()

    def get_task(self, task_id: str) -> Optional[dict]:
        """
        获取任务信息（自动清理过期任务）

        Args:
            task_id: 任务ID

        Returns:
            任务对象，如果不存在或已过期返回 None
        """
        with self._task_lock:
            # 先清理过期任务（懒加载清理，已经持有锁）
            self._cleanup_expired_tasks(require_lock=False)
            
            task = self.tasks.get(task_id)
            
            # 如果任务存在但已过期，返回 None
            if task and task.get("scheduled_delete_at"):
                try:
                    delete_time = datetime.fromisoformat(task["scheduled_delete_at"])
                    if delete_time <= datetime.now():
                        del self.tasks[task_id]
                        self._save_to_file()
                        return None
                except (ValueError, TypeError):
                    pass
            
            return task

    def get_all_tasks(self) -> List[dict]:
        """
        获取所有任务（自动清理过期任务）

        Returns:
            任务列表（不包含过期任务）
        """
        with self._task_lock:
            # 先清理过期任务（已经持有锁）
            self._cleanup_expired_tasks(require_lock=False)
            return list(self.tasks.values())

    def delete_task(self, task_id: str):
        """
        删除任务

        Args:
            task_id: 任务ID
        """
        with self._task_lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                self._save_to_file()
                logger.info(f"🗑️  任务已删除: {task_id}")

    def schedule_delete_task(self, task_id: str, delay_seconds: int = 300):
        """
        计划延迟删除任务（用于失败任务，保留一段时间供前端查询）
        
        使用基于时间戳的机制，即使服务器重启也能正确清理过期任务

        Args:
            task_id: 任务ID
            delay_seconds: 延迟删除时间（秒），默认300秒（5分钟）
        """
        with self._task_lock:
            if task_id not in self.tasks:
                logger.warning(f"⚠️ 无法计划删除不存在的任务: {task_id}")
                return
            
            # 计算计划删除时间
            delete_time = datetime.now().timestamp() + delay_seconds
            scheduled_delete_at = datetime.fromtimestamp(delete_time).isoformat()
            
            # 在任务中记录计划删除时间
            self.tasks[task_id]["scheduled_delete_at"] = scheduled_delete_at
            self._save_to_file()
            
            logger.info(f"📅 已计划在 {delay_seconds} 秒后删除任务: {task_id} (计划删除时间: {scheduled_delete_at})")


# 全局单例实例
task_manager = TaskManager()
