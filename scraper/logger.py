import json
import os
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from . import config


class RunLogger:
    def __init__(
        self,
        component: str,
        run_type: str,
        manga_slug: Optional[str] = None,
        manga_name: Optional[str] = None,
        start_url: Optional[str] = None,
        chapter_count: Optional[int] = None,
        chapter_range: Optional[str] = None,
        allowed_formats: Optional[List[str]] = None,
    ):
        self.run_id = str(uuid.uuid4())
        self.component = component
        self.run_type = run_type
        self.manga_slug = manga_slug
        self.manga_name = manga_name
        self.start_url = start_url
        self.chapter_count = chapter_count
        self.chapter_range = chapter_range
        self.allowed_formats = allowed_formats or ["jpg"]
        self.indexer_triggered = False
        self.files_written = 0
        self.resume_enabled = False
        self.skipped_chapters: List[int] = []
        self.downloaded_chapters: List[int] = []
        self.interrupted_at: Optional[str] = None
        self.last_completed_chapter: Optional[int] = None
        self.start_time = datetime.now()
        self.filename = f"{component}_{int(time.time())}.json"
        self.filepath = os.path.join(config.RUN_LOGS_PATH, self.filename)
        self.error: Optional[str] = None
        self.status: str = "running"
        self.stats = {"manga": 0, "chapters": 0, "pages": 0}
        self.fallback_class_used: Optional[str] = None
        self.source_pattern_detected: Optional[str] = None
        self._write()

    def _to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "component": self.component,
            "type": self.run_type,
            "manga_slug": self.manga_slug,
            "manga_name": self.manga_name,
            "start_url": self.start_url,
            "chapter_count": self.chapter_count,
            "chapter_range": self.chapter_range,
            "allowed_formats": self.allowed_formats,
            "started_at": self.start_time.isoformat(),
            "finished_at": datetime.now().isoformat() if self.status in ("success", "partial", "failed", "interrupted") else None,
            "status": self.status,
            "error": self.error,
            "files_written": self.files_written,
            "indexer_triggered": self.indexer_triggered,
            "stats": self.stats,
            "resume_enabled": self.resume_enabled,
            "skipped_chapters": self.skipped_chapters,
            "downloaded_chapters": self.downloaded_chapters,
            "interrupted_at": self.interrupted_at,
            "last_completed_chapter": self.last_completed_chapter,
            "fallback_class_used": self.fallback_class_used,
            "source_pattern_detected": self.source_pattern_detected,
        }

    def _write(self):
        try:
            os.makedirs(config.RUN_LOGS_PATH, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._to_dict(), f, indent=2)
        except Exception:
            pass

    def update_stats(self, manga: int = 0, chapters: int = 0, pages: int = 0):
        self.stats["manga"] += manga
        self.stats["chapters"] += chapters
        self.stats["pages"] += pages

    def add_files_written(self, count: int):
        self.files_written += max(0, int(count))

    def set_indexer_triggered(self, value: bool = True):
        self.indexer_triggered = bool(value)
        self._write()

    def finish(self, status: str = "success"):
        self.status = status
        self._write()

    def fail(self, error: str):
        self.error = error
        self.status = "failed"
        self._write()

    def mark_interrupted(self, error: str):
        self.error = error
        self.status = "interrupted"
        self.interrupted_at = datetime.now().isoformat()
        self._write()
