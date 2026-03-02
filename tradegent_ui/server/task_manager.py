"""Task manager for long-running agent operations."""
import asyncio
import time
import uuid
import structlog
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncGenerator

log = structlog.get_logger(__name__)


class TaskState(Enum):
    """Task execution states."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentTask:
    """A long-running agent task."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    intent: str = ""
    query: str = ""
    tickers: list[str] = field(default_factory=list)
    state: TaskState = TaskState.PENDING
    progress: int = 0  # 0-100
    messages: list[str] = field(default_factory=list)
    result: dict | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        """Convert task to dict for serialization."""
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "intent": self.intent,
            "query": self.query,
            "tickers": self.tickers,
            "state": self.state.value,
            "progress": self.progress,
            "messages": self.messages[-10:],  # Last 10 messages
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def add_message(self, message: str):
        """Add a progress message."""
        self.messages.append(message)

    def update_progress(self, progress: int, message: str | None = None):
        """Update progress and optionally add message."""
        self.progress = min(max(progress, 0), 100)
        if message:
            self.add_message(message)


class TaskManager:
    """Manages long-running agent tasks with progress streaming.

    Handles:
    - Task submission and queueing
    - Progress tracking
    - Concurrent task limits
    - Task cleanup
    """

    def __init__(self, max_concurrent: int = 3):
        """Initialize task manager.

        Args:
            max_concurrent: Maximum concurrent tasks
        """
        self._tasks: dict[str, AgentTask] = {}
        self._queue: asyncio.Queue[AgentTask] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._max_concurrent = max_concurrent
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self):
        """Start task worker pool."""
        if self._running:
            return

        self._running = True

        # Start worker tasks
        for i in range(self._max_concurrent):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

        log.info("Task manager started", workers=self._max_concurrent)

    async def stop(self):
        """Stop task worker pool."""
        self._running = False

        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass

        self._workers.clear()
        log.info("Task manager stopped")

    async def submit(
        self,
        session_id: str,
        intent: str,
        query: str,
        tickers: list[str] | None = None,
    ) -> str:
        """Submit a new task.

        Args:
            session_id: Session identifier
            intent: Task intent
            query: User query
            tickers: Relevant tickers

        Returns:
            Task ID
        """
        task = AgentTask(
            session_id=session_id,
            intent=intent,
            query=query,
            tickers=tickers or [],
            state=TaskState.QUEUED,
        )

        async with self._lock:
            self._tasks[task.task_id] = task
            queue_size = self._queue.qsize()
            total_tasks = len(self._tasks)

        await self._queue.put(task)

        log.info(
            "task.submitted",
            task_id=task.task_id,
            session_id=session_id,
            intent=intent,
            tickers=tickers or [],
            query_length=len(query),
            queue_size=queue_size + 1,
            total_tasks=total_tasks,
        )

        return task.task_id

    async def get_task(self, task_id: str) -> AgentTask | None:
        """Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            AgentTask or None if not found
        """
        return self._tasks.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled, False if not found or already completed
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
            return False

        task.state = TaskState.CANCELLED
        task.completed_at = datetime.utcnow()
        log.info("Task cancelled", task_id=task_id)

        return True

    async def stream_progress(self, task_id: str) -> AsyncGenerator[dict, None]:
        """Stream task progress updates.

        Args:
            task_id: Task ID

        Yields:
            Progress update dicts
        """
        task = self._tasks.get(task_id)
        if not task:
            yield {"error": "Task not found", "task_id": task_id}
            return

        last_progress = -1
        last_message_count = 0

        while task.state not in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
            # Only yield if something changed
            if task.progress != last_progress or len(task.messages) != last_message_count:
                last_progress = task.progress
                last_message_count = len(task.messages)

                yield {
                    "type": "progress",
                    "task_id": task_id,
                    "state": task.state.value,
                    "progress": task.progress,
                    "message": task.messages[-1] if task.messages else None,
                }

            await asyncio.sleep(0.5)

        # Final update
        if task.state == TaskState.COMPLETED:
            yield {
                "type": "complete",
                "task_id": task_id,
                "state": task.state.value,
                "progress": 100,
                "result": task.result,
            }
        else:
            yield {
                "type": "error",
                "task_id": task_id,
                "state": task.state.value,
                "error": task.error or "Task failed",
            }

    async def _worker(self, worker_id: int):
        """Worker coroutine for processing tasks.

        Args:
            worker_id: Worker identifier
        """
        log.info("Task worker started", worker_id=worker_id)

        while self._running:
            try:
                # Get next task from queue (with timeout to check running flag)
                try:
                    task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Skip cancelled tasks
                if task.state == TaskState.CANCELLED:
                    self._queue.task_done()
                    continue

                # Process task
                await self._process_task(task, worker_id)
                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Worker error", worker_id=worker_id, error=str(e))

        log.info("Task worker stopped", worker_id=worker_id)

    async def _process_task(self, task: AgentTask, worker_id: int):
        """Process a single task.

        Args:
            task: Task to process
            worker_id: Worker identifier
        """
        start_time = time.perf_counter()

        log.info(
            "task.processing.started",
            task_id=task.task_id,
            session_id=task.session_id,
            worker_id=worker_id,
            intent=task.intent,
            tickers=task.tickers,
            query_preview=task.query[:50] if task.query else "",
        )

        task.state = TaskState.RUNNING
        task.started_at = datetime.utcnow()
        task.add_message("Starting task...")

        try:
            # Import coordinator here to avoid circular imports
            from agent.coordinator import get_coordinator

            coordinator = await get_coordinator()

            # Update progress
            task.update_progress(10, "Classifying intent...")
            log.debug("task.progress", task_id=task.task_id, progress=10, stage="classify")
            await asyncio.sleep(0.1)  # Allow progress to stream

            task.update_progress(20, "Routing to specialist agent...")
            log.debug("task.progress", task_id=task.task_id, progress=20, stage="route")
            await asyncio.sleep(0.1)

            task.state = TaskState.STREAMING
            task.update_progress(30, "Executing tools...")
            log.debug("task.progress", task_id=task.task_id, progress=30, stage="execute")

            # Process query
            process_start = time.perf_counter()
            response = await coordinator.process(task.session_id, task.query)
            process_ms = (time.perf_counter() - process_start) * 1000

            task.update_progress(80, "Generating response...")
            log.debug("task.progress", task_id=task.task_id, progress=80, stage="generate")
            await asyncio.sleep(0.1)

            if response.success:
                task.state = TaskState.COMPLETED
                task.result = response.a2ui
                task.update_progress(100, "Task completed successfully")

                duration_ms = (time.perf_counter() - start_time) * 1000
                component_count = len(response.a2ui.get("components", [])) if response.a2ui else 0

                log.info(
                    "task.processing.completed",
                    task_id=task.task_id,
                    session_id=task.session_id,
                    worker_id=worker_id,
                    success=True,
                    component_count=component_count,
                    process_ms=round(process_ms, 2),
                    duration_ms=round(duration_ms, 2),
                )
            else:
                task.state = TaskState.FAILED
                task.error = response.error or "Unknown error"
                task.add_message(f"Task failed: {task.error}")

                duration_ms = (time.perf_counter() - start_time) * 1000
                log.warning(
                    "task.processing.failed",
                    task_id=task.task_id,
                    session_id=task.session_id,
                    worker_id=worker_id,
                    error=task.error,
                    duration_ms=round(duration_ms, 2),
                )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            log.error(
                "task.processing.error",
                task_id=task.task_id,
                session_id=task.session_id,
                worker_id=worker_id,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
            )
            task.state = TaskState.FAILED
            task.error = str(e)
            task.add_message(f"Error: {e}")

        finally:
            task.completed_at = datetime.utcnow()

    async def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove completed tasks older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours
        """
        now = datetime.utcnow()
        to_remove = []

        async with self._lock:
            for task_id, task in self._tasks.items():
                if task.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
                    age = (now - task.created_at).total_seconds() / 3600
                    if age > max_age_hours:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]

        if to_remove:
            log.info("Cleaned up old tasks", count=len(to_remove))

    def get_stats(self) -> dict:
        """Get task manager statistics.

        Returns:
            Dict with stats
        """
        states = {}
        for task in self._tasks.values():
            state = task.state.value
            states[state] = states.get(state, 0) + 1

        return {
            "total_tasks": len(self._tasks),
            "queue_size": self._queue.qsize(),
            "workers": len(self._workers),
            "running": self._running,
            "states": states,
        }


# Global task manager instance
_task_manager: TaskManager | None = None


async def get_task_manager() -> TaskManager:
    """Get or create the global task manager."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager(max_concurrent=3)
        await _task_manager.start()
    return _task_manager
