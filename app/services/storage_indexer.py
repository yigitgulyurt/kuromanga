# Filesystem-based manga indexer for the web app (consumer-only).

import os
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app import db
from app.models.manga import Manga
from app.models.chapter import Chapter
from app.models.page import Page


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_LAST_SCAN_TS: Optional[float] = None
_SCAN_INTERVAL_SEC: int = 60


def _is_image_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in IMAGE_EXTS


def _humanize_title_from_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


def _parse_chapter_number(name: str) -> Optional[int]:
    digits = "".join(ch for ch in name if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _ensure_manga(slug: str) -> Manga:
    title = _humanize_title_from_slug(slug)
    existing = Manga.query.filter_by(title=title).first()
    if existing:
        return existing
    m = Manga(title=title, description=None)
    db.session.add(m)
    db.session.commit()
    return m


def _ensure_chapter(manga_id: int, chapter_number: int, title: Optional[str]) -> Chapter:
    existing = (
        Chapter.query.filter_by(manga_id=manga_id, number=chapter_number).first()
    )
    if existing:
        return existing
    ch = Chapter(manga_id=manga_id, number=chapter_number, title=title)
    db.session.add(ch)
    db.session.commit()
    return ch


def _ensure_page(chapter_id: int, page_number: int, image_path: str) -> Page:
    existing = (
        Page.query.filter_by(chapter_id=chapter_id, number=page_number).first()
    )
    if existing:
        return existing
    pg = Page(chapter_id=chapter_id, number=page_number, image_path=image_path)
    db.session.add(pg)
    db.session.commit()
    return pg


def _scan_one_chapter_dir(manga_slug: str, chapter_dir: Path) -> Tuple[int, int]:
    chapter_number = _parse_chapter_number(chapter_dir.name)
    if chapter_number is None:
        return (0, 0)

    images = sorted([p for p in chapter_dir.iterdir() if _is_image_file(p)])
    if not images:
        return (0, 0)

    manga = _ensure_manga(manga_slug)
    chapter_title = f"Chapter {chapter_number}"
    chapter = _ensure_chapter(manga.id, chapter_number, chapter_title)

    total = len(images)
    for idx, img in enumerate(images, start=1):
        width = max(3, len(str(total)))
        padded = str(idx).zfill(width)
        # Build web-visible path under /storage/manga/...
        web_path = f"/storage/manga/{manga_slug}/{chapter_dir.name}/{img.name}"
        _ensure_page(chapter.id, idx, web_path)

    return (1, total)


def _scan_manga_slug_dir(slug_dir: Path) -> Tuple[int, int]:
    if not slug_dir.is_dir():
        return (0, 0)
    chapter_dirs = [p for p in slug_dir.iterdir() if p.is_dir()]
    chapters_added = 0
    pages_added = 0
    for ch in chapter_dirs:
        c_added, p_added = _scan_one_chapter_dir(slug_dir.name, ch)
        chapters_added += c_added
        pages_added += p_added
    return (chapters_added, pages_added)


def _write_indexer_log(run_logs_path: str, status: str, stats: Dict, start_time: datetime, error: Optional[str] = None):
    if not run_logs_path:
        return
    
    filename = f"indexer_{int(start_time.timestamp())}.json"
    filepath = os.path.join(run_logs_path, filename)
    
    data = {
        "component": "indexer",
        "started_at": start_time.isoformat(),
        "finished_at": datetime.now().isoformat() if status in ("success", "failed") else None,
        "status": status,
        "stats": stats,
        "error": error
    }
    
    try:
        os.makedirs(run_logs_path, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def index_storage(base_path: str, run_logs_path: str = None, force: bool = False) -> Dict[str, int]:
    global _LAST_SCAN_TS

    start_time = datetime.now()
    stats = {"manga": 0, "chapters": 0, "pages": 0}
    
    if run_logs_path:
        _write_indexer_log(run_logs_path, "running", stats, start_time)

    now = time.time()
    if not force and _LAST_SCAN_TS and (now - _LAST_SCAN_TS) < _SCAN_INTERVAL_SEC:
        if run_logs_path:
            # Skip update, but maybe log that it was skipped? 
            # Or just don't log "running" if skipped?
            # User requirement: "Indexer çalışmaya başladığında... log oluştur"
            # But if we return early, we technically didn't run a full scan.
            # I will just return early without logging success/fail if skipped.
            # But wait, I already logged "running". I should update to "success" (skipped).
             _write_indexer_log(run_logs_path, "success", stats, start_time, error="Skipped (cached)")
        return {"status": 0, "manga_dirs": 0, "chapters_added": 0, "pages_added": 0}

    try:
        root = Path(base_path)
        if not root.exists() or not root.is_dir():
            if run_logs_path:
                _write_indexer_log(run_logs_path, "failed", stats, start_time, error="Storage path not found")
            return {"status": 0, "manga_dirs": 0, "chapters_added": 0, "pages_added": 0}

        manga_dirs = [p for p in root.iterdir() if p.is_dir()]
        chapters_total = 0
        pages_total = 0
        
        # Update stats for "manga" count (directories found)
        # Note: Indexer logic counts 'chapters_added' and 'pages_added' (newly added).
        # But 'stats' in log should probably reflect what was processed or added.
        # I'll stick to what the function returns: added counts.
        
        for slug_dir in manga_dirs:
            c_added, p_added = _scan_manga_slug_dir(slug_dir)
            chapters_total += c_added
            pages_total += p_added
        
        _LAST_SCAN_TS = now
        
        stats["manga"] = len(manga_dirs) # Just count of dirs scanned
        stats["chapters"] = chapters_total
        stats["pages"] = pages_total

        if run_logs_path:
             _write_indexer_log(run_logs_path, "success", stats, start_time)

        return {
            "status": 1,
            "manga_dirs": len(manga_dirs),
            "chapters_added": chapters_total,
            "pages_added": pages_total,
        }
    except Exception as e:
        if run_logs_path:
            _write_indexer_log(run_logs_path, "failed", stats, start_time, error=str(e))
        raise e

