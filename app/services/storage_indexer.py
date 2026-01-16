# Filesystem-based manga indexer for the web app (consumer-only).

import os
import time
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

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
        if not existing.slug:
            existing.slug = Manga.slugify(title)
            db.session.commit()
        return existing
    m = Manga(title=title, slug=Manga.slugify(title), description=None)
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


def _collect_fs_state(root: Path) -> Tuple[Dict[str, Dict[int, Tuple[str, List[Path]]]], Set[str], bool, int, int]:
    state: Dict[str, Dict[int, Tuple[str, List[Path]]]] = {}
    slugs: Set[str] = set()
    partial = False
    chapters_count = 0
    pages_count = 0
    for slug_dir in [p for p in root.iterdir() if p.is_dir()]:
        slug = slug_dir.name
        slugs.add(slug)
        state.setdefault(slug, {})
        for ch_dir in [p for p in slug_dir.iterdir() if p.is_dir()]:
            num = _parse_chapter_number(ch_dir.name)
            if num is None:
                partial = True
                continue
            images = sorted([p for p in ch_dir.iterdir() if _is_image_file(p)])
            if not images:
                partial = True
                continue
            state[slug][num] = (ch_dir.name, images)
            chapters_count += 1
            pages_count += len(images)
    return state, slugs, partial, chapters_count, pages_count


def _remove_manga(m: Manga) -> int:
    chapters_removed = 0
    for ch in Chapter.query.filter_by(manga_id=m.id).all():
        for pg in Page.query.filter_by(chapter_id=ch.id).all():
            db.session.delete(pg)
        db.session.delete(ch)
        chapters_removed += 1
    db.session.delete(m)
    db.session.commit()
    return chapters_removed


def _synch_manga(slug: str, chapters_map: Dict[int, Tuple[str, List[Path]]], stats: Dict[str, int]) -> None:
    title = _humanize_title_from_slug(slug)
    manga = Manga.query.filter_by(title=title).first()
    if manga is None:
        manga = Manga(title=title, slug=Manga.slugify(title), description=None)
        db.session.add(manga)
        db.session.commit()
        stats["added_manga"] += 1
    elif not manga.slug:
        manga.slug = Manga.slugify(title)
        db.session.commit()
    fs_chapter_numbers = set(chapters_map.keys())
    db_chapters = Chapter.query.filter_by(manga_id=manga.id).all()
    for ch in db_chapters:
        if ch.number not in fs_chapter_numbers:
            for pg in Page.query.filter_by(chapter_id=ch.id).all():
                db.session.delete(pg)
            db.session.delete(ch)
            stats["removed_chapters"] += 1
    db.session.commit()
    for ch_num, (ch_dir_name, images) in sorted(chapters_map.items(), key=lambda x: x[0]):
        chapter = Chapter.query.filter_by(manga_id=manga.id, number=ch_num).first()
        if chapter is None:
            chapter = Chapter(manga_id=manga.id, number=ch_num, title=f"Chapter {ch_num}")
            db.session.add(chapter)
            db.session.commit()
            stats["added_chapters"] += 1
        target_total = len(images)
        existing_pages = Page.query.filter_by(chapter_id=chapter.id).all()
        for pg in existing_pages:
            if pg.number < 1 or pg.number > target_total:
                db.session.delete(pg)
        db.session.commit()
        for idx, img in enumerate(images, start=1):
            web_path = f"/storage/manga/{slug}/{ch_dir_name}/{img.name}"
            existing = Page.query.filter_by(chapter_id=chapter.id, number=idx).first()
            if existing is None:
                new_pg = Page(chapter_id=chapter.id, number=idx, image_path=web_path)
                db.session.add(new_pg)
                stats["pages_added"] += 1
            else:
                if existing.image_path != web_path:
                    existing.image_path = web_path
        db.session.commit()


def _write_indexer_log(run_logs_path: str, status: str, stats: Dict, start_time: datetime, error: Optional[str] = None, processed_slugs: Optional[List[str]] = None, files_written: int = 0, chapter_range: Optional[str] = None):
    if not run_logs_path:
        return
    filename = f"indexer_{int(start_time.timestamp())}.json"
    filepath = os.path.join(run_logs_path, filename)
    data = {
        "run_id": str(uuid.uuid4()),
        "component": "indexer",
        "type": "index",
        "manga_slug": None,
        "manga_name": None,
        "start_url": None,
        "chapter_count": None,
        "chapter_range": chapter_range,
        "allowed_formats": None,
        "started_at": start_time.isoformat(),
        "finished_at": datetime.now().isoformat() if status in ("success", "partial", "failed") else None,
        "status": status,
        "error": error,
        "files_written": files_written,
        "indexer_triggered": False,
        "stats": stats,
        "processed_slugs": processed_slugs or [],
    }
    try:
        os.makedirs(run_logs_path, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def index_storage(base_path: str, run_logs_path: str = None, force: bool = False) -> Dict[str, int]:
    start_time = datetime.now()
    stats = {
        "manga": 0,
        "chapters": 0,
        "pages": 0,
        "added_manga": 0,
        "added_chapters": 0,
        "removed_manga": 0,
        "removed_chapters": 0,
        "pages_added": 0,
    }
    if run_logs_path:
        _write_indexer_log(run_logs_path, "running", stats, start_time)
    try:
        root = Path(base_path)
        if not base_path or not root.exists() or not root.is_dir():
            if run_logs_path:
                _write_indexer_log(run_logs_path, "failed", stats, start_time, error="Storage path not found", processed_slugs=[], files_written=0, chapter_range=None)
            return {
                "status": 0,
                "manga_dirs": 0,
                "chapters_added": 0,
                "pages_added": 0,
                "removed_manga": 0,
                "removed_chapters": 0,
            }
        fs_state, fs_slugs, partial, chapters_count, pages_count = _collect_fs_state(root)
        stats["manga"] = len(fs_slugs)
        stats["chapters"] = chapters_count
        stats["pages"] = pages_count
        processed_slugs = sorted(list(fs_slugs))
        db_mangas = Manga.query.all()
        fs_titles = set(_humanize_title_from_slug(s) for s in fs_slugs)
        for m in db_mangas:
            if m.title not in fs_titles:
                removed = _remove_manga(m)
                stats["removed_manga"] += 1
                stats["removed_chapters"] += removed
        for slug, chapters_map in fs_state.items():
            _synch_manga(slug, chapters_map, stats)
        status_str = "success" if not partial else "partial"
        if run_logs_path:
            _write_indexer_log(run_logs_path, status_str, stats, start_time, error=None if status_str == "success" else "Some entries skipped", processed_slugs=processed_slugs, files_written=stats["pages_added"], chapter_range=None)
        return {
            "status": 1 if status_str == "success" else 2,
            "manga_dirs": len(fs_slugs),
            "chapters_added": stats["added_chapters"],
            "pages_added": stats["pages_added"],
            "removed_manga": stats["removed_manga"],
            "removed_chapters": stats["removed_chapters"],
        }
    except Exception as e:
        if run_logs_path:
            _write_indexer_log(run_logs_path, "failed", stats, start_time, error=str(e), processed_slugs=[], files_written=0, chapter_range=None)
        raise e
