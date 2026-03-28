"""
任务调度模块 - 定时内容生成调度器
Task Scheduler Module - Scheduled content generation

使用 APScheduler 实现定时任务，支持 Redis 队列（可选，降级到内存队列）。
"""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("social-bot.scheduler")

# ---------------------------------------------------------------------------
# 尝试导入可选依赖
# ---------------------------------------------------------------------------
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    logger.warning("APScheduler 未安装，调度功能不可用")

try:
    import redis.asyncio as aioredis

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    logger.info("redis 未安装，使用内存队列")


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledTask(BaseModel):
    """调度任务记录"""
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    platform: str = ""
    topic: str = ""
    language: str = "auto"
    extra_instructions: str = ""
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# 内存任务队列（Redis 不可用时的降级方案）
# ---------------------------------------------------------------------------

class InMemoryTaskQueue:
    """基于字典的简易内存任务队列，仅用于单进程场景。"""

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}

    async def push(self, task: ScheduledTask) -> str:
        self._tasks[task.task_id] = task
        logger.info("任务入队 [内存]: %s", task.task_id)
        return task.task_id

    async def get(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    async def update(self, task_id: str, **kwargs: Any) -> None:
        task = self._tasks.get(task_id)
        if task:
            for k, v in kwargs.items():
                if hasattr(task, k):
                    setattr(task, k, v)

    async def list_all(self, status: Optional[TaskStatus] = None) -> list[ScheduledTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    async def delete(self, task_id: str) -> bool:
        return self._tasks.pop(task_id, None) is not None


# ---------------------------------------------------------------------------
# Redis 任务队列
# ---------------------------------------------------------------------------

class RedisTaskQueue:
    """基于 Redis Hash 的任务队列，支持多进程 / 多实例共享。"""

    HASH_KEY = "social-bot:tasks"

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis: aioredis.Redis = aioredis.from_url(
            redis_url, decode_responses=True
        )

    async def push(self, task: ScheduledTask) -> str:
        await self._redis.hset(self.HASH_KEY, task.task_id, task.model_dump_json())
        logger.info("任务入队 [Redis]: %s", task.task_id)
        return task.task_id

    async def get(self, task_id: str) -> Optional[ScheduledTask]:
        raw = await self._redis.hget(self.HASH_KEY, task_id)
        if raw:
            return ScheduledTask.model_validate_json(raw)
        return None

    async def update(self, task_id: str, **kwargs: Any) -> None:
        task = await self.get(task_id)
        if task:
            for k, v in kwargs.items():
                if hasattr(task, k):
                    setattr(task, k, v)
            await self._redis.hset(self.HASH_KEY, task.task_id, task.model_dump_json())

    async def list_all(self, status: Optional[TaskStatus] = None) -> list[ScheduledTask]:
        raw_map = await self._redis.hgetall(self.HASH_KEY)
        tasks = [ScheduledTask.model_validate_json(v) for v in raw_map.values()]
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    async def delete(self, task_id: str) -> bool:
        removed = await self._redis.hdel(self.HASH_KEY, task_id)
        return removed > 0


# ---------------------------------------------------------------------------
# 调度器管理器
# ---------------------------------------------------------------------------

class ContentScheduler:
    """
    内容生成调度器。

    用法示例::

        scheduler = ContentScheduler()
        scheduler.start()

        # 定时任务：在指定时间生成内容
        task_id = await scheduler.schedule_generation(
            platform="xiaohongshu",
            topic="秋季护肤好物推荐",
            run_at=datetime(2026, 3, 28, 10, 0, 0),
        )

        # 查询任务状态
        task = await scheduler.get_task(task_id)
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        generate_fn=None,
    ) -> None:
        """
        Args:
            redis_url: Redis 连接地址，为 None 时使用内存队列。
            generate_fn: 内容生成的异步可调用对象，签名:
                         async def fn(platform, topic, language, extra) -> str
        """
        # 选择队列后端
        if redis_url and HAS_REDIS:
            self._queue = RedisTaskQueue(redis_url)
            logger.info("使用 Redis 任务队列: %s", redis_url)
        else:
            self._queue = InMemoryTaskQueue()
            logger.info("使用内存任务队列")

        # APScheduler 实例
        self._scheduler: Optional[AsyncIOScheduler] = None
        if HAS_APSCHEDULER:
            self._scheduler = AsyncIOScheduler()
        else:
            logger.warning("APScheduler 不可用，仅支持即时任务")

        # 内容生成回调
        self._generate_fn = generate_fn

    # ------ 生命周期 ------

    def start(self) -> None:
        """启动调度器"""
        if self._scheduler and not self._scheduler.running:
            self._scheduler.start()
            logger.info("调度器已启动")

    def shutdown(self) -> None:
        """关闭调度器"""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("调度器已关闭")

    # ------ 任务管理 ------

    async def schedule_generation(
        self,
        platform: str,
        topic: str,
        *,
        run_at: Optional[datetime] = None,
        cron: Optional[str] = None,
        interval_minutes: Optional[int] = None,
        language: str = "auto",
        extra_instructions: str = "",
    ) -> str:
        """
        调度一个内容生成任务。

        三种触发方式（互斥）:
          - run_at: 在指定时间执行一次
          - cron: cron 表达式，周期执行
          - interval_minutes: 每隔 N 分钟执行

        Returns:
            task_id
        """
        task = ScheduledTask(
            platform=platform,
            topic=topic,
            language=language,
            extra_instructions=extra_instructions,
            scheduled_at=run_at,
        )
        await self._queue.push(task)

        # 如果调度器可用，注册定时任务
        if self._scheduler:
            if run_at:
                trigger = DateTrigger(run_date=run_at)
            elif cron:
                trigger = CronTrigger.from_crontab(cron)
            elif interval_minutes:
                trigger = IntervalTrigger(minutes=interval_minutes)
            else:
                # 立即执行
                trigger = DateTrigger(run_date=datetime.utcnow())

            self._scheduler.add_job(
                self._execute_task,
                trigger=trigger,
                args=[task.task_id],
                id=task.task_id,
                name=f"gen:{platform}:{topic[:20]}",
                replace_existing=True,
            )
            logger.info("已注册调度任务: %s", task.task_id)
        else:
            # 无调度器，立即执行
            await self._execute_task(task.task_id)

        return task.task_id

    async def _execute_task(self, task_id: str) -> None:
        """执行单个任务"""
        task = await self._queue.get(task_id)
        if not task:
            logger.error("任务不存在: %s", task_id)
            return

        await self._queue.update(task_id, status=TaskStatus.RUNNING)
        logger.info("开始执行任务: %s [%s] %s", task_id, task.platform, task.topic)

        try:
            if self._generate_fn:
                result = await self._generate_fn(
                    task.platform,
                    task.topic,
                    task.language,
                    task.extra_instructions,
                )
            else:
                result = f"[模拟生成] 平台={task.platform}, 主题={task.topic}"

            await self._queue.update(
                task_id,
                status=TaskStatus.COMPLETED,
                completed_at=datetime.utcnow(),
                result=result,
            )
            logger.info("任务完成: %s", task_id)

        except Exception as exc:
            await self._queue.update(
                task_id,
                status=TaskStatus.FAILED,
                completed_at=datetime.utcnow(),
                error=str(exc),
            )
            logger.error("任务失败: %s - %s", task_id, exc)

    async def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """查询任务状态"""
        return await self._queue.get(task_id)

    async def list_tasks(self, status: Optional[TaskStatus] = None) -> list[ScheduledTask]:
        """列出所有任务"""
        return await self._queue.list_all(status)

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = await self._queue.get(task_id)
        if not task:
            return False

        # 从调度器移除
        if self._scheduler:
            try:
                self._scheduler.remove_job(task_id)
            except Exception:
                pass

        await self._queue.update(task_id, status=TaskStatus.CANCELLED)
        logger.info("任务已取消: %s", task_id)
        return True
