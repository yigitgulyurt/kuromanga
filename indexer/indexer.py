import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

from app import create_app
from flask import current_app
from app.models.manga import Manga
from app.models.chapter import Chapter
from app.models.page import Page
from app.services.storage_indexer import (
    index_storage,
    _collect_fs_state,
    _humanize_title_from_slug,
    _write_indexer_log,
    _synch_manga,
    _remove_manga,
)


def _compute_diff_stats_for_all(base_path: str) -> Tuple[Dict[str, int], List[str], bool]:
    root = Path(base_path)
    fs_state, fs_slugs, partial, chapters_count, pages_count = _collect_fs_state(root)
    stats = {
        "manga": len(fs_slugs),
        "chapters": chapters_count,
        "pages": pages_count,
        "added_manga": 0,
        "added_chapters": 0,
        "removed_manga": 0,
        "removed_chapters": 0,
        "pages_added": 0,
    }
    db_mangas = Manga.query.all()
    db_titles: Set[str] = set(m.title for m in db_mangas)
    fs_titles = set(_humanize_title_from_slug(s) for s in fs_slugs)
    for title in db_titles:
        if title not in fs_titles:
            m = Manga.query.filter_by(title=title).first()
            if m:
                stats["removed_manga"] += 1
                stats["removed_chapters"] += Chapter.query.filter_by(manga_id=m.id).count()
    for slug in fs_slugs:
        title = _humanize_title_from_slug(slug)
        m = Manga.query.filter_by(title=title).first()
        chapters_map = fs_state.get(slug, {})
        if not m:
            stats["added_manga"] += 1
            stats["added_chapters"] += len(chapters_map)
            for ch_num, (_, images) in chapters_map.items():
                existing_pages = 0
                stats["pages_added"] += max(0, len(images) - existing_pages)
            continue
        db_chapters = Chapter.query.filter_by(manga_id=m.id).all()
        db_ch_nums = set(ch.number for ch in db_chapters)
        fs_ch_nums = set(chapters_map.keys())
        for db_ch in db_chapters:
            if db_ch.number not in fs_ch_nums:
                stats["removed_chapters"] += 1
        for ch_num, (_, images) in chapters_map.items():
            if ch_num not in db_ch_nums:
                stats["added_chapters"] += 1
                stats["pages_added"] += len(images)
            else:
                chapter = Chapter.query.filter_by(manga_id=m.id, number=ch_num).first()
                if chapter:
                    existing_pages = Page.query.filter_by(chapter_id=chapter.id).count()
                    if len(images) > existing_pages:
                        stats["pages_added"] += (len(images) - existing_pages)
    return stats, sorted(list(fs_slugs)), partial


def _compute_diff_stats_for_slug(base_path: str, slug: str) -> Tuple[Dict[str, int], List[str], bool]:
    root = Path(base_path)
    fs_state, fs_slugs, partial, chapters_count, pages_count = _collect_fs_state(root)
    stats = {
        "manga": 1 if slug in fs_slugs else 0,
        "chapters": sum(len(fs_state.get(slug, {})) for _ in [0]) if slug in fs_slugs else 0,
        "pages": sum(len(v[1]) for v in fs_state.get(slug, {}).values()) if slug in fs_slugs else 0,
        "added_manga": 0,
        "added_chapters": 0,
        "removed_manga": 0,
        "removed_chapters": 0,
        "pages_added": 0,
    }
    title = _humanize_title_from_slug(slug)
    m = Manga.query.filter_by(title=title).first()
    slug_in_fs = slug in fs_slugs
    chapters_map = fs_state.get(slug, {})
    if not slug_in_fs and m:
        stats["removed_manga"] += 1
        stats["removed_chapters"] += Chapter.query.filter_by(manga_id=m.id).count()
        return stats, [slug] if slug_in_fs else [], partial
    if slug_in_fs and not m:
        stats["added_manga"] += 1
        stats["added_chapters"] += len(chapters_map)
        for _, images in chapters_map.values():
            stats["pages_added"] += len(images)
        return stats, [slug], partial
    if slug_in_fs and m:
        db_chapters = Chapter.query.filter_by(manga_id=m.id).all()
        db_ch_nums = set(ch.number for ch in db_chapters)
        fs_ch_nums = set(chapters_map.keys())
        for db_ch in db_chapters:
            if db_ch.number not in fs_ch_nums:
                stats["removed_chapters"] += 1
        for ch_num, (_, images) in chapters_map.items():
            if ch_num not in db_ch_nums:
                stats["added_chapters"] += 1
                stats["pages_added"] += len(images)
            else:
                chapter = Chapter.query.filter_by(manga_id=m.id, number=ch_num).first()
                if chapter:
                    existing_pages = Page.query.filter_by(chapter_id=chapter.id).count()
                    if len(images) > existing_pages:
                        stats["pages_added"] += (len(images) - existing_pages)
    return stats, [slug] if slug_in_fs else [], partial


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run filesystem-to-DB indexer independently.")
    parser.add_argument("--manga-slug", help="Synchronize only the specified manga slug.")
    parser.add_argument("--all", action="store_true", help="Synchronize entire filesystem.")
    parser.add_argument("--dry-run", action="store_true", help="Only compute and log diffs; do not modify DB.")
    parser.add_argument("--verbose", action="store_true", help="Print detailed output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app()
    with app.app_context():
        base = current_app.config.get("STORAGE_MANGA_PATH")
        logs = current_app.config.get("STORAGE_RUN_LOGS_PATH")
        start_time = datetime.now()
        if args.dry_run:
            if args.manga_slug:
                stats, slugs, partial = _compute_diff_stats_for_slug(base, args.manga_slug)
                status = "success" if not partial else "partial"
                _write_indexer_log(logs, status, stats, start_time, error=None if status == "success" else "Some entries skipped", processed_slugs=slugs, files_written=stats.get("pages_added", 0), chapter_range=None)
                if args.verbose:
                    sys.stdout.write(str(stats) + os.linesep)
            elif args.all:
                stats, slugs, partial = _compute_diff_stats_for_all(base)
                status = "success" if not partial else "partial"
                _write_indexer_log(logs, status, stats, start_time, error=None if status == "success" else "Some entries skipped", processed_slugs=slugs, files_written=stats.get("pages_added", 0), chapter_range=None)
                if args.verbose:
                    sys.stdout.write(str(stats) + os.linesep)
            else:
                sys.stdout.write("Specify --all or --manga-slug for dry-run" + os.linesep)
                raise SystemExit(2)
        else:
            if args.manga_slug:
                root = Path(base)
                fs_state, fs_slugs, partial, chapters_count, pages_count = _collect_fs_state(root)
                stats = {
                    "manga": 1 if args.manga_slug in fs_slugs else 0,
                    "chapters": sum(len(fs_state.get(args.manga_slug, {})) for _ in [0]) if args.manga_slug in fs_slugs else 0,
                    "pages": sum(len(v[1]) for v in fs_state.get(args.manga_slug, {}).values()) if args.manga_slug in fs_slugs else 0,
                    "added_manga": 0,
                    "added_chapters": 0,
                    "removed_manga": 0,
                    "removed_chapters": 0,
                    "pages_added": 0,
                }
                title = _humanize_title_from_slug(args.manga_slug)
                m = Manga.query.filter_by(title=title).first()
                if args.manga_slug not in fs_slugs and m:
                    removed = _remove_manga(m)
                    stats["removed_manga"] += 1
                    stats["removed_chapters"] += removed
                    status = "success"
                    _write_indexer_log(logs, status, stats, start_time, error=None, processed_slugs=[args.manga_slug], files_written=0, chapter_range=None)
                    if args.verbose:
                        sys.stdout.write(str(stats) + os.linesep)
                else:
                    chapters_map = fs_state.get(args.manga_slug, {})
                    _synch_manga(args.manga_slug, chapters_map, stats)
                    status = "success" if not partial else "partial"
                    _write_indexer_log(logs, status, stats, start_time, error=None if status == "success" else "Some entries skipped", processed_slugs=[args.manga_slug], files_written=stats.get("pages_added", 0), chapter_range=None)
                    if args.verbose:
                        sys.stdout.write(str(stats) + os.linesep)
            elif args.all:
                result = index_storage(base, run_logs_path=logs, force=True)
                if args.verbose:
                    sys.stdout.write(str(result) + os.linesep)
            else:
                sys.stdout.write("Specify --all or --manga-slug" + os.linesep)
                raise SystemExit(2)


if __name__ == "__main__":
    main()

