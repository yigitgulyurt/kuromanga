import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.models.manga import Manga
from app.models.chapter import Chapter
from app.models.page import Page


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_LAST_CHECK_TS: Optional[float] = None
_LAST_RESULT: Optional[Dict] = None
_CACHE_SEC = 30


def _is_image_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in IMAGE_EXTS


def _slugify_title(title: str) -> str:
    s = title.strip().lower()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in {" ", "-", "_"}:
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "manga"


def _chapter_number_from_name(name: str) -> Optional[int]:
    digits = "".join(ch for ch in name if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _scan_disk(base_path: str) -> Dict[str, Dict]:
    root = Path(base_path)
    result = {}
    if not root.exists() or not root.is_dir():
        return result
    for slug_dir in root.iterdir():
        if not slug_dir.is_dir():
            continue
        chapters = {}
        for ch_dir in slug_dir.iterdir():
            if not ch_dir.is_dir():
                continue
            num = _chapter_number_from_name(ch_dir.name)
            if num is None:
                continue
            imgs = sorted([p for p in ch_dir.iterdir() if _is_image_file(p)])
            if not imgs:
                continue
            chapters[num] = {"dir": ch_dir, "images": imgs}
        result[slug_dir.name] = {"chapters": chapters}
    return result


def _db_index() -> Dict[str, Dict]:
    dbi = {}
    mangas = Manga.query.all()
    for m in mangas:
        dbi[m.id] = {
            "title": m.title,
            "slug": _slugify_title(m.title),
            "chapters": {},
        }
    chapters = Chapter.query.all()
    for ch in chapters:
        if ch.manga_id in dbi:
            dbi[ch.manga_id]["chapters"][ch.number] = {
                "id": ch.id,
                "pages": {},
            }
    pages = Page.query.all()
    for p in pages:
        for m_id, m_info in dbi.items():
            chs = m_info["chapters"]
            for num, ci in chs.items():
                if ci["id"] == p.chapter_id:
                    ci["pages"][p.number] = {
                        "id": p.id,
                        "path": p.image_path or "",
                    }
                    break
    return dbi


def storage_health(base_path: str, force: bool = False) -> Dict:
    global _LAST_CHECK_TS, _LAST_RESULT

    now = time.time()
    if not force and _LAST_CHECK_TS and _LAST_RESULT and (now - _LAST_CHECK_TS) < _CACHE_SEC:
        return _LAST_RESULT

    disk = _scan_disk(base_path)
    dbi = _db_index()

    missing_on_disk = {
        "manga": [],
        "chapters": [],
        "pages": [],
    }
    missing_in_db = {
        "chapters": [],
        "images": [],
    }
    broken_chapters: List[Dict] = []

    for m_id, m_info in dbi.items():
        slug = m_info["slug"]
        disk_manga = disk.get(slug)
        if not disk_manga:
            missing_on_disk["manga"].append(
                {"manga_id": m_id, "title": m_info["title"], "slug": slug}
            )
            continue
        for ch_num, ci in m_info["chapters"].items():
            disk_ch = disk_manga["chapters"].get(ch_num)
            if not disk_ch:
                missing_on_disk["chapters"].append(
                    {
                        "manga_id": m_id,
                        "title": m_info["title"],
                        "chapter_id": ci["id"],
                        "chapter_number": ch_num,
                    }
                )
            else:
                for p_num, pi in ci["pages"].items():
                    path = pi["path"]
                    if path and path.startswith("/storage/manga/"):
                        rel = path.replace("/storage/manga/", "")
                        fs_path = os.path.join(base_path, rel.replace("/", os.sep))
                        if not os.path.exists(fs_path):
                            missing_on_disk["pages"].append(
                                {
                                    "chapter_id": ci["id"],
                                    "page_id": pi["id"],
                                    "page_number": p_num,
                                    "expected_path": fs_path,
                                }
                            )
                    else:
                        pass

    for slug, s_info in disk.items():
        title = " ".join(slug.replace("-", " ").replace("_", " ").split()).title()
        m_match = None
        for m_id, m_info in dbi.items():
            if m_info["title"] == title:
                m_match = (m_id, m_info)
                break
        for ch_num, ch_info in s_info["chapters"].items():
            if not m_match:
                missing_in_db["chapters"].append(
                    {
                        "slug": slug,
                        "title": title,
                        "chapter_number": ch_num,
                        "reason": "manga_not_found",
                    }
                )
                continue
            m_id, m_info = m_match
            db_ch = m_info["chapters"].get(ch_num)
            if not db_ch:
                missing_in_db["chapters"].append(
                    {
                        "slug": slug,
                        "title": title,
                        "chapter_number": ch_num,
                        "reason": "chapter_not_found",
                    }
                )
                continue
            images = ch_info["images"]
            total = len(images)
            for idx, img in enumerate(images, start=1):
                if idx not in db_ch["pages"]:
                    missing_in_db["images"].append(
                        {
                            "chapter_id": db_ch["id"],
                            "page_number": idx,
                            "file": str(img),
                        }
                    )

    for m_id, m_info in dbi.items():
        for ch_num, ci in m_info["chapters"].items():
            if not ci["pages"]:
                continue
            nums = sorted(ci["pages"].keys())
            expected = list(range(1, nums[-1] + 1))
            missing_seq = [n for n in expected if n not in nums]
            if missing_seq:
                broken_chapters.append(
                    {
                        "manga_id": m_id,
                        "title": m_info["title"],
                        "chapter_id": ci["id"],
                        "chapter_number": ch_num,
                        "missing_sequence": missing_seq,
                    }
                )

    result = {
        "missing_on_disk": missing_on_disk,
        "missing_in_db": missing_in_db,
        "broken_chapters": broken_chapters,
    }
    _LAST_CHECK_TS = now
    _LAST_RESULT = result
    return result

