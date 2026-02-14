import asyncio
import threading
from typing import Dict, Optional, List, Set
from queue import Queue

class TaskManager:
    def __init__(self):
        self.tasks: Dict[int, dict] = {}
        self.lock = threading.Lock()

    def start_task(self, source_id: int):
        with self.lock:
            self.tasks[source_id] = {
                "stop_event": threading.Event(),
                "consumers": set(),
                "status": "running",
                "history": []
            }
            res = self.tasks[source_id]["stop_event"]
        return res

    def stop_task(self, source_id: int):
        with self.lock:
            if source_id in self.tasks:
                self.tasks[source_id]["stop_event"].set()
                self.tasks[source_id]["status"] = "cancelling"
                self._add_log_unlocked(source_id, "🛑 Cancellation signal sent...")

    def get_log_queue(self, source_id: int) -> Optional[Queue]:
        with self.lock:
            if source_id not in self.tasks:
                return None

            q = Queue()
            for log in self.tasks[source_id]["history"]:
                q.put(log)

            self.tasks[source_id]["consumers"].add(q)
            return q

    def remove_log_queue(self, source_id: int, q: Queue):
        with self.lock:
            if source_id in self.tasks:
                self.tasks[source_id]["consumers"].discard(q)

    def _add_log_unlocked(self, source_id: int, message: str, type: str = "log", data: dict = None):
        if source_id in self.tasks:
            payload = {"type": type, "message": message}
            if data:
                payload.update(data)
            self.tasks[source_id]["history"].append(payload)
            if len(self.tasks[source_id]["history"]) > 100:
                self.tasks[source_id]["history"].pop(0)
            for q in self.tasks[source_id]["consumers"]:
                q.put(payload)

    def add_log(self, source_id: int, message: str, type: str = "log", data: dict = None):
        with self.lock:
            self._add_log_unlocked(source_id, message, type, data)

    def finish_task(self, source_id: int, status: str = "finished"):
        with self.lock:
            if source_id in self.tasks:
                self.tasks[source_id]["status"] = status
                for q in self.tasks[source_id]["consumers"]:
                    q.put(None)

    def cleanup_task(self, source_id: int):
        with self.lock:
            if source_id in self.tasks:
                del self.tasks[source_id]

    def is_task_running(self, source_id: int) -> bool:
        with self.lock:
            return source_id in self.tasks and self.tasks[source_id]["status"] == "running"

task_manager = TaskManager()
