import json
import os
import time
from datetime import datetime
from typing import Optional, Dict

from . import config


class RunLogger:
    def __init__(self, component: str):
        self.component = component
        self.start_time = datetime.now()
        self.filename = f"{component}_{int(time.time())}.json"
        self.filepath = os.path.join(config.RUN_LOGS_PATH, self.filename)
        self.stats = {"manga": 0, "chapters": 0, "pages": 0}
        
        self._write_log("running")

    def _write_log(self, status: str, error: Optional[str] = None):
        data = {
            "component": self.component,
            "started_at": self.start_time.isoformat(),
            "finished_at": datetime.now().isoformat() if status in ("success", "failed") else None,
            "status": status,
            "stats": self.stats,
            "error": error
        }
        
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            # Fallback: print to stderr if logging fails, but don't crash app logic
            print(f"Failed to write run log: {e}", file=sys.stderr)

    def update_stats(self, manga: int = 0, chapters: int = 0, pages: int = 0):
        self.stats["manga"] += manga
        self.stats["chapters"] += chapters
        self.stats["pages"] += pages
        # Optional: update file on progress? No, keeps IO low. Only on finish.

    def finish(self):
        self._write_log("success")

    def fail(self, error: str):
        self._write_log("failed", error)
