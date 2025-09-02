# 文件路径: agent/tasks.py (新建)
# -*- coding: utf-8 -*-

import asyncio
import logging
import time
import uuid
from collections import deque
from threading import Lock
from typing import Optional

# 从 agent 模块导入依赖，而不是 main
from agent.generators.flow_automator import generate_video_in_flow

log = logging.getLogger("videoagent")
MAX_CONCURRENT_FLOW_TASKS = 5

class FlowTaskManager:
    def __init__(self):
        self.task_queue = deque()
        self.running_tasks = {}
        self.lock = Lock()
        self.worker_task = None
        log.info("✅ FlowTaskManager initialized.")

    def add_task(self, prompt_content: str, debugging_port: Optional[int], flow_url: Optional[str]) -> str:
        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id,
            "status": "queued",
            "submitted_at": time.time(),
            "details": {
                "prompt_content": prompt_content,
                "debugging_port": debugging_port,
                "flow_url": flow_url
            }
        }
        with self.lock:
            self.task_queue.append(task)
        log.info(f"📥 Task {task_id} added to Flow queue. Queue size: {len(self.task_queue)}")
        return task_id

    async def worker(self):
        log.info("🧑‍🏭 Flow task worker started.")
        while True:
            task_to_run = None
            with self.lock:
                if self.task_queue and len(self.running_tasks) < MAX_CONCURRENT_FLOW_TASKS:
                    task_to_run = self.task_queue.popleft()
                    task_to_run["status"] = "running"
                    task_to_run["started_at"] = time.time()
                    self.running_tasks[task_to_run["task_id"]] = task_to_run
                    log.info(f"▶️ Starting task {task_to_run['task_id']}. Active tasks: {len(self.running_tasks)}")

            if task_to_run:
                try:
                    result = await asyncio.to_thread(
                        generate_video_in_flow,
                        task_to_run["details"]["prompt_content"],
                        task_to_run["details"]["debugging_port"],
                        task_to_run["details"]["flow_url"]
                    )
                    log.info(f"✅ Task {task_to_run['task_id']} finished. Result: {result.get('message')}")
                    task_to_run["result"] = result
                except Exception as e:
                    log.error(f"❌ Task {task_to_run['task_id']} failed with exception: {e}")
                    task_to_run["result"] = {"success": False, "message": str(e)}
                finally:
                    with self.lock:
                        if task_to_run["task_id"] in self.running_tasks:
                            del self.running_tasks[task_to_run['task_id']]
                        log.info(f"⏹️ Task {task_to_run['task_id']} removed from active list. Active tasks: {len(self.running_tasks)}")

            await asyncio.sleep(5)

    def start_worker(self):
        if self.worker_task is None:
            self.worker_task = asyncio.create_task(self.worker())
            log.info("Worker task created.")

# 创建一个谁都可以引用的全局实例
flow_task_manager = FlowTaskManager()
