# 文件路径: agent/tasks.py (新建)
# -*- coding: utf-8 -*-

import asyncio
import logging
import time
import uuid
from collections import deque
from threading import Lock
from typing import Optional, Dict, Any

# 从 agent 模块导入依赖，而不是 main
from agent.generators.flow_automator import generate_video_in_flow

log = logging.getLogger("videoagent")
MAX_CONCURRENT_FLOW_TASKS = 5

class FlowTaskManager:
    def __init__(self):
        self.task_queue = deque()
        self.running_tasks = {}
        self.completed_tasks = {}  # 记录已完成的任务
        self.failed_tasks = {}     # 记录失败的任务
        self.lock = Lock()
        self.worker_task = None
        self.browser_locks = {}    # 浏览器端口锁，防止端口冲突
        self.task_history = deque(maxlen=100)  # 任务历史记录
        self.start_time = time.time()  # 记录启动时间
        log.info("✅ FlowTaskManager initialized with enhanced features.")

    def add_task(self, prompt_content: str, debugging_port: Optional[int], flow_url: Optional[str]) -> str:
        # 检查是否已有相同内容的任务在队列中
        with self.lock:
            for existing_task in self.task_queue:
                if existing_task["details"]["prompt_content"] == prompt_content:
                    log.warning(f"⚠️ Duplicate task detected for content: {prompt_content[:50]}...")
                    return existing_task["task_id"]
            
            # 检查是否在运行中
            for task_id, running_task in self.running_tasks.items():
                if running_task["details"]["prompt_content"] == prompt_content:
                    log.warning(f"⚠️ Task already running for content: {prompt_content[:50]}...")
                    return task_id
        
        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id,
            "status": "queued",
            "submitted_at": time.time(),
            "retry_count": 0,
            "max_retries": 2,
            "details": {
                "prompt_content": prompt_content,
                "debugging_port": debugging_port,
                "flow_url": flow_url
            }
        }
        
        with self.lock:
            self.task_queue.append(task)
            self.task_history.append({
                "task_id": task_id,
                "action": "added",
                "timestamp": time.time(),
                "queue_size": len(self.task_queue)
            })
        
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
                    # 添加任务间延迟，避免浏览器冲突
                    if len(self.running_tasks) > 1:
                        delay = 3.0  # 多个任务运行时增加延迟
                        log.info(f"⏳ Adding delay {delay}s to avoid browser conflicts...")
                        await asyncio.sleep(delay)
                    
                    # 检查浏览器端口是否被占用
                    debugging_port = task_to_run["details"]["debugging_port"]
                    if debugging_port and debugging_port in self.browser_locks:
                        log.warning(f"⚠️ Port {debugging_port} is locked, waiting...")
                        await asyncio.sleep(2.0)
                    
                    # 锁定浏览器端口
                    if debugging_port:
                        self.browser_locks[debugging_port] = task_to_run["task_id"]
                    
                    try:
                        result = await asyncio.to_thread(
                            generate_video_in_flow,
                            task_to_run["details"]["prompt_content"],
                            debugging_port,
                            task_to_run["details"]["flow_url"]
                        )
                        
                        if result.get("success"):
                            log.info(f"✅ Task {task_to_run['task_id']} finished successfully: {result.get('message')}")
                            task_to_run["result"] = result
                            task_to_run["status"] = "completed"
                            
                            with self.lock:
                                self.completed_tasks[task_to_run["task_id"]] = task_to_run
                        else:
                            # 任务失败，检查是否需要重试
                            if task_to_run["retry_count"] < task_to_run["max_retries"]:
                                task_to_run["retry_count"] += 1
                                log.warning(f"🔄 Task {task_to_run['task_id']} failed, retrying ({task_to_run['retry_count']}/{task_to_run['max_retries']})")
                                
                                # 重新加入队列
                                with self.lock:
                                    self.task_queue.append(task_to_run)
                                    self.task_history.append({
                                        "task_id": task_to_run["task_id"],
                                        "action": "retry",
                                        "timestamp": time.time(),
                                        "retry_count": task_to_run["retry_count"]
                                    })
                                continue
                            else:
                                log.error(f"❌ Task {task_to_run['task_id']} failed after {task_to_run['max_retries']} retries")
                                task_to_run["result"] = result
                                task_to_run["status"] = "failed"
                                
                                with self.lock:
                                    self.failed_tasks[task_to_run["task_id"]] = task_to_run
                        
                    finally:
                        # 释放浏览器端口锁
                        if debugging_port and debugging_port in self.browser_locks:
                            del self.browser_locks[debugging_port]
                            
                except Exception as e:
                    log.error(f"❌ Task {task_to_run['task_id']} failed with exception: {e}")
                    task_to_run["result"] = {"success": False, "message": str(e)}
                    task_to_run["status"] = "failed"
                    
                    # 检查是否需要重试
                    if task_to_run["retry_count"] < task_to_run["max_retries"]:
                        task_to_run["retry_count"] += 1
                        log.warning(f"🔄 Task {task_to_run['task_id']} exception, retrying ({task_to_run['retry_count']}/{task_to_run['max_retries']})")
                        
                        with self.lock:
                            self.task_queue.append(task_to_run)
                        continue
                    else:
                        with self.lock:
                            self.failed_tasks[task_to_run["task_id"]] = task_to_run
                
                finally:
                    with self.lock:
                        if task_to_run["task_id"] in self.running_tasks:
                            del self.running_tasks[task_to_run['task_id']]
                        log.info(f"⏹️ Task {task_to_run['task_id']} removed from active list. Active tasks: {len(self.running_tasks)}")

            await asyncio.sleep(5)

    def start_worker(self):
        if self.worker_task is None:
            try:
                # 获取当前事件循环，如果没有则创建新的
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # 如果没有运行中的事件循环，创建一个新的
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # 启动主worker
                self.worker_task = loop.create_task(self.worker())
                
                # 启动清理任务
                cleanup_task = loop.create_task(self._cleanup_worker())
                
                log.info("✅ Worker task and cleanup task created successfully.")
            except Exception as e:
                log.error(f"❌ Failed to create worker task: {e}")
                # 如果异步启动失败，使用线程方式
                import threading
                def run_worker():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.worker())
                    except Exception as e:
                        log.error(f"❌ Worker thread failed: {e}")
                
                worker_thread = threading.Thread(target=run_worker, daemon=True)
                worker_thread.start()
                log.info("✅ Worker started in separate thread.")
    
    async def _cleanup_worker(self):
        """定期清理过期任务的worker"""
        log.info("🧹 Cleanup worker started.")
        while True:
            try:
                await asyncio.sleep(3600)  # 每小时清理一次
                self.clear_completed_tasks(max_age_hours=24)
            except Exception as e:
                log.error(f"❌ Cleanup worker error: {e}")
                await asyncio.sleep(300)  # 出错后等待5分钟再试

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取指定任务的详细状态"""
        with self.lock:
            if task_id in self.running_tasks:
                return self.running_tasks[task_id]
            elif task_id in self.completed_tasks:
                return self.completed_tasks[task_id]
            elif task_id in self.failed_tasks:
                return self.failed_tasks[task_id]
            else:
                # 检查是否在队列中
                for task in self.task_queue:
                    if task["task_id"] == task_id:
                        return task
        return None
    
    def get_queue_summary(self) -> Dict[str, Any]:
        """获取队列摘要信息"""
        with self.lock:
            return {
                "queued": len(self.task_queue),
                "running": len(self.running_tasks),
                "completed": len(self.completed_tasks),
                "failed": len(self.failed_tasks),
                "total": len(self.task_queue) + len(self.running_tasks) + len(self.completed_tasks) + len(self.failed_tasks),
                "browser_locks": list(self.browser_locks.keys()),
                "recent_history": list(self.task_history)[-10:] if self.task_history else []
            }
    
    def clear_completed_tasks(self, max_age_hours: int = 24):
        """清理过期的已完成任务"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        with self.lock:
            # 清理过期的已完成任务
            expired_completed = [
                task_id for task_id, task in self.completed_tasks.items()
                if current_time - task.get("started_at", 0) > max_age_seconds
            ]
            for task_id in expired_completed:
                del self.completed_tasks[task_id]
            
            # 清理过期的失败任务
            expired_failed = [
                task_id for task_id, task in self.failed_tasks.items()
                if current_time - task.get("started_at", 0) > max_age_seconds
            ]
            for task_id in expired_failed:
                del self.failed_tasks[task_id]
            
            if expired_completed or expired_failed:
                log.info(f"🧹 Cleaned up {len(expired_completed)} completed and {len(expired_failed)} failed tasks")

# 创建一个谁都可以引用的全局实例
flow_task_manager = FlowTaskManager()
