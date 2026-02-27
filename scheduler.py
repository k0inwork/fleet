import asyncio
import logging
from enum import Enum
from typing import Dict, List, Set, Optional
from pydantic import BaseModel
from brain import Task, TaskGraph

logger = logging.getLogger("Scheduler")

class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICTED = "conflicted"

class TaskNode(BaseModel):
    task: Task
    status: TaskStatus = TaskStatus.PENDING
    session_id: Optional[str] = None

class DAGScheduler:
    def __init__(self, task_graph: TaskGraph):
        self.nodes: Dict[str, TaskNode] = {t.id: TaskNode(task=t) for t in task_graph.tasks}
        self.completed_tasks: Set[str] = set()
        self.update_ready_tasks()

    def update_ready_tasks(self):
        for node in self.nodes.values():
            if node.status == TaskStatus.PENDING:
                if all(dep in self.completed_tasks for dep in node.task.dependencies):
                    node.status = TaskStatus.READY

    def get_ready_tasks(self) -> List[str]:
        return [task_id for task_id, node in self.nodes.items() if node.status == TaskStatus.READY]

    def mark_running(self, task_id: str, session_id: str):
        if task_id in self.nodes:
            self.nodes[task_id].status = TaskStatus.RUNNING
            self.nodes[task_id].session_id = session_id

    def mark_completed(self, task_id: str):
        if task_id in self.nodes:
            self.nodes[task_id].status = TaskStatus.COMPLETED
            self.completed_tasks.add(task_id)
            self.update_ready_tasks()

    def mark_failed(self, task_id: str):
        if task_id in self.nodes:
            self.nodes[task_id].status = TaskStatus.FAILED

    def mark_conflicted(self, task_id: str):
        if task_id in self.nodes:
            self.nodes[task_id].status = TaskStatus.CONFLICTED

    def is_finished(self) -> bool:
        return all(node.status in {TaskStatus.COMPLETED, TaskStatus.FAILED} for node in self.nodes.values())

    def get_all_status(self) -> Dict[str, TaskStatus]:
        return {task_id: node.status for task_id, node in self.nodes.items()}
