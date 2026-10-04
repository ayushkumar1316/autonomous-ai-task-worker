"""Task scheduler — cron-style recurring tasks and multi-task orchestration."""
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ScheduleRule:
    """Cron-style rule: run at fixed interval or specific times."""
    frequency: str  # "once", "daily", "hourly", "interval"
    interval_seconds: int = 0  # for "interval" frequency
    by_day: List[str] = field(default_factory=list)  # for "daily": ["Mon", "Wed"]
    by_hour: List[int] = field(default_factory=list)  # for "daily": [9, 15]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_occurrences: int = 0  # 0 = unlimited

    def next_run(self, from_time: Optional[datetime] = None) -> Optional[datetime]:
        """Compute next occurrence, or None if rule is exhausted."""
        if from_time is None:
            from_time = datetime.now()
        if self.start_date and from_time < self.start_date:
            from_time = self.start_date
        if self.end_date and from_time > self.end_date:
            return None

        if self.frequency == "once":
            if self.start_date and from_time < self.start_date:
                return self.start_date
            return None  # Already passed

        if self.frequency == "interval":
            if self.interval_seconds <= 0:
                return None
            # Find next slot
            elapsed = (from_time - (self.start_date or from_time)).total_seconds()
            next_idx = elapsed // self.interval_seconds + 1
            next_time = (self.start_date or from_time) + timedelta(seconds=next_idx * self.interval_seconds)
            return next_time if (self.end_date is None or next_time <= self.end_date) else None

        if self.frequency in ("daily", "hourly"):
            # Simplified: next occurrence at same time tomorrow/hourly
            if self.frequency == "daily":
                next_time = from_time + timedelta(days=1)
            else:
                next_time = from_time + timedelta(hours=1)
            # Adjust for by_day/by_hour if specified
            if self.by_day:
                while next_time.strftime("%a") not in self.by_day:
                    next_time += timedelta(days=1)
            if self.by_hour:
                while next_time.hour not in self.by_hour:
                    next_time += timedelta(hours=1)
            return next_time if (self.end_date is None or next_time <= self.end_date) else None

        return None

@dataclass
class ScheduledTask:
    """A task with its schedule and execution state."""
    name: str
    goal: str
    schedule: ScheduleRule
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    history: List[Dict] = field(default_factory=list)

class TaskScheduler:
    """Orchestrates multiple scheduled tasks, supports cron-style rules."""

    def __init__(self, worker_fn: Callable):
        """worker_fn: callable(goal, ...) -> Dict with 'status', 'result', etc.

        The worker_fn may accept an optional ``executor`` kwarg to reuse a
        shared ActionExecutor (one Playwright browser) across runs instead of
        relaunching Chromium every time.
        """
        self.worker_fn = worker_fn
        self.tasks: Dict[str, ScheduledTask] = {}
        self._task_counter = 0

    def add_task(self, name: str, goal: str, schedule: ScheduleRule) -> ScheduledTask:
        """Register a new scheduled task."""
        self._task_counter += 1
        task_id = f"task_{self._task_counter:03d}"
        task = ScheduledTask(
            name=name,
            goal=goal,
            schedule=schedule,
            task_id=task_id,
            next_run=schedule.next_run()
        )
        self.tasks[task_id] = task
        return task

    def run_due_tasks(self) -> List[Dict]:
        """Execute all tasks that are due now. Returns list of results."""
        results = []
        now = datetime.now()
        for task in list(self.tasks.values()):
            if task.next_run and now >= task.next_run:
                result = self._execute_task(task)
                results.append(result)
                # Compute next run
                task.next_run = task.schedule.next_run(now)
                if task.next_run is None:
                    task.status = TaskStatus.COMPLETED
        return results

    def run_forever(self, max_iterations: int = 10, interval_seconds: int = 5):
        """Run the scheduler loop for a limited number of iterations."""
        all_results = []
        for i in range(max_iterations):
            results = self.run_due_tasks()
            all_results.extend(results)
            if results:
                print(f"[scheduler] Iteration {i+1}: executed {len(results)} task(s)")
            time.sleep(interval_seconds)
        return all_results

    def run_all_now(self) -> List[Dict]:
        """Force-run all tasks regardless of schedule."""
        results = []
        for task in list(self.tasks.values()):
            result = self._execute_task(task)
            results.append(result)
        return results

    def _execute_task(self, task: ScheduledTask, executor=None) -> Dict:
        """Execute a single task and record the result.

        ``executor`` is forwarded to the worker when it accepts it, so a
        Playwright browser can be reused across runs.
        """
        print(f"[scheduler] Executing: {task.name} (run #{task.run_count + 1})")
        task.status = TaskStatus.RUNNING
        task.last_run = datetime.now()

        try:
            if executor is not None:
                result = self.worker_fn(task.goal, executor=executor)
            else:
                result = self.worker_fn(task.goal)
            task.run_count += 1
            task.status = TaskStatus.COMPLETED if result.get("status") == "completed" else TaskStatus.FAILED

            record = {
                "task_id": task.task_id,
                "name": task.name,
                "executed_at": task.last_run.isoformat(),
                "run_count": task.run_count,
                "result": result,
                "status": task.status.value
            }
            task.history.append(record)
            return record
        except Exception as e:
            task.status = TaskStatus.FAILED
            record = {
                "task_id": task.task_id,
                "name": task.name,
                "executed_at": task.last_run.isoformat(),
                "run_count": task.run_count,
                "error": str(e),
                "status": "failed"
            }
            task.history.append(record)
            return record

    def get_task_summary(self) -> Dict:
        """Return summary of all tasks."""
        summary = {"total": len(self.tasks), "completed": 0, "failed": 0, "pending": 0}
        for task in self.tasks.values():
            if task.status == TaskStatus.COMPLETED:
                summary["completed"] += 1
            elif task.status == TaskStatus.FAILED:
                summary["failed"] += 1
            else:
                summary["pending"] += 1
        return summary
