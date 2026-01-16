# Command line scraper for downloading a single manga chapter's images.

import argparse
import os
import re
import sys
import subprocess
import signal
from typing import List, Set, Optional
from urllib.parse import urljoin, urlparse
from .logger import RunLogger

from bs4 import BeautifulSoup

from . import config
from .downloader import DownloadError, download_image, fetch_html


CURRENT_LOGGER: Optional[RunLogger] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download manga chapter images from a given URL.",
    )
    parser.add_argument(
        "--manga-url",
        required=True,
        help="URL of the manga chapter page to scrape.",
    )
    parser.add_argument(
        "--manga-name",
        required=True,
        help="Human readable manga name (used for storage slug and logs).",
    )
    parser.add_argument(
        "--formats",
        default="jpg",
        help="Comma-separated list of allowed image formats (e.g., jpg,png,webp). Default: jpg",
    )
    parser.add_argument(
        "--start-url",
        help="Starting chapter URL for multi-chapter scraping.",
    )
    parser.add_argument(
        "--chapters",
        type=int,
        help="Number of chapters to scrape starting from --start-url (auto-increment).",
    )
    parser.add_argument(
        "--rename-only",
        action="store_true",
        help="Do not download; rename existing chapter files to zero-padded canonical format.",
    )
    parser.add_argument(
        "--run-indexer",
        action="store_true",
        help="After scraping/renaming, trigger the indexer via subprocess (keeps scraper decoupled).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip already-downloaded chapters/pages based on filesystem state.",
    )
    return parser.parse_args()


def derive_manga_slug(chapter_url: str) -> str:
    parsed = urlparse(chapter_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        base = parsed.netloc or "manga"
    else:
        base = segments[0]
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", base).strip("-").lower()
    return slug or "manga"


def derive_chapter_number(chapter_url: str) -> str:
    parsed = urlparse(chapter_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    candidate = segments[-1] if segments else ""
    digits = re.findall(r"\d+", candidate)
    if digits:
        return digits[-1]
    return "1"


def extract_image_urls(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        absolute = urljoin(base_url, src)
        if not absolute:
            continue
        lower = absolute.lower()
        if not (
            lower.endswith(".jpg")
            or lower.endswith(".jpeg")
            or lower.endswith(".png")
            or lower.endswith(".webp")
        ):
            continue
        candidates.append(absolute)

    seen = set()
    unique_urls: List[str] = []
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        unique_urls.append(url)

    return unique_urls


def build_output_directory(manga_slug: str, chapter_number: str) -> str:
    return os.path.join(config.BASE_STORAGE_PATH, manga_slug, chapter_number)


def is_chapter_complete(manga_slug: str, chapter_number: str) -> bool:
    chapter_dir = build_output_directory(manga_slug, chapter_number)
    if not os.path.isdir(chapter_dir):
        return False
    files = [f for f in os.listdir(chapter_dir) if os.path.isfile(os.path.join(chapter_dir, f))]
    return len(files) > 0


def determine_filename(index: int, total: int, image_url: str) -> str:
    width = max(3, len(str(total)))
    parsed = urlparse(image_url)
    _, ext = os.path.splitext(parsed.path)
    if not ext:
        ext = ".jpg"
    padded_index = str(index).zfill(width)
    return f"{padded_index}{ext}"

def rename_chapter_files_count(manga_slug: str, chapter_number: str) -> int:
    chapter_dir = build_output_directory(manga_slug, chapter_number)
    if not os.path.isdir(chapter_dir):
        return 0
    files = [f for f in os.listdir(chapter_dir) if os.path.isfile(os.path.join(chapter_dir, f))]
    files.sort()
    total = len(files)
    width = max(3, len(str(total)))
    renamed = 0
    for idx, fname in enumerate(files, start=1):
        _, ext = os.path.splitext(fname)
        ext = (ext or ".jpg").lower()
        target = f"{str(idx).zfill(width)}{ext}"
        if fname != target:
            src_path = os.path.join(chapter_dir, fname)
            dst_path = os.path.join(chapter_dir, target)
            if os.path.exists(dst_path):
                tmp_path = os.path.join(chapter_dir, f"__tmp_{idx}{ext}")
                os.replace(src_path, tmp_path)
                os.replace(tmp_path, dst_path)
            else:
                os.replace(src_path, dst_path)
            renamed += 1
    return renamed


def slugify_name(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-") or "manga"


def parse_formats_arg(formats_arg: str) -> Set[str]:
    allowed = set()
    for part in (formats_arg or "").split(","):
        p = part.strip().lower()
        if p in {"jpg", "jpeg"}:
            allowed.update({".jpg", ".jpeg"})
        elif p == "png":
            allowed.add(".png")
        elif p == "webp":
            allowed.add(".webp")
        # silently ignore invalid tokens
    if not allowed:
        allowed.update({".jpg", ".jpeg"})
    return allowed


def filter_by_formats(urls: List[str], allowed_exts: Set[str]) -> List[str]:
    result = []
    for u in urls:
        parsed = urlparse(u)
        _, ext = os.path.splitext(parsed.path.lower())
        if ext in allowed_exts:
            result.append(u)
    return result


def increment_chapter_url(base_url: str, next_chapter_number: int) -> str:
    parsed = urlparse(base_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        return base_url
    last = segments[-1]
    if re.search(r"\d+", last):
        new_last = re.sub(r"(\d+)(?!.*\d)", str(next_chapter_number), last, count=1)
    else:
        new_last = f"{last}-{next_chapter_number}"
    segments[-1] = new_last
    new_path = "/" + "/".join(segments)
    return parsed._replace(path=new_path).geturl()


def rename_chapter_files(manga_slug: str, chapter_number: str) -> str:
    chapter_dir = build_output_directory(manga_slug, chapter_number)
    if not os.path.isdir(chapter_dir):
        return chapter_dir
    files = [f for f in os.listdir(chapter_dir) if os.path.isfile(os.path.join(chapter_dir, f))]
    files.sort()
    total = len(files)
    width = max(3, len(str(total)))
    for idx, fname in enumerate(files, start=1):
        _, ext = os.path.splitext(fname)
        ext = (ext or ".jpg").lower()
        target = f"{str(idx).zfill(width)}{ext}"
        if fname != target:
            src_path = os.path.join(chapter_dir, fname)
            dst_path = os.path.join(chapter_dir, target)
            if os.path.exists(dst_path):
                tmp_path = os.path.join(chapter_dir, f"__tmp_{idx}{ext}")
                os.replace(src_path, tmp_path)
                os.replace(tmp_path, dst_path)
            else:
                os.replace(src_path, dst_path)
    return chapter_dir


def _signal_handler(signum, frame):
    global CURRENT_LOGGER
    name = None
    try:
        if signum == signal.SIGINT:
            name = "SIGINT"
        else:
            sigterm = getattr(signal, "SIGTERM", None)
            if sigterm is not None and signum == sigterm:
                name = "SIGTERM"
    except Exception:
        name = None

    if name is None:
        name = str(signum)

    if CURRENT_LOGGER is not None:
        try:
            CURRENT_LOGGER.mark_interrupted(f"Interrupted by signal {name}")
        except Exception:
            pass
    raise SystemExit(1)


def trigger_indexer_subprocess() -> None:
    try:
        cmd = [
            sys.executable,
            "-c",
            (
                "import os;"
                "from app.services.storage_indexer import index_storage;"
                "base=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage','manga');"
                "logs=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage','run_logs');"
                "print(index_storage(base, run_logs_path=logs, force=True))"
            ),
        ]
        subprocess.run(cmd, check=False)
    except Exception:
        pass


def scrape_chapter(chapter_url: str, manga_slug: str, allowed_exts: Set[str], logger: RunLogger, resume: bool = False) -> str:
    html = fetch_html(chapter_url)

    image_urls = extract_image_urls(html, chapter_url)
    if not image_urls:
        raise RuntimeError("No image URLs were found on the provided page.")

    chapter_number = derive_chapter_number(chapter_url)
    output_dir = build_output_directory(manga_slug, chapter_number)
    os.makedirs(output_dir, exist_ok=True)

    image_urls = filter_by_formats(image_urls, allowed_exts)
    total = len(image_urls)
    logger.update_stats(manga=1, chapters=1, pages=total)
    for index, image_url in enumerate(image_urls, start=1):
        filename = determine_filename(index, total, image_url)
        destination_path = os.path.join(output_dir, filename)
        if resume and os.path.exists(destination_path):
            continue
        download_image(image_url, destination_path)

    return output_dir


def main() -> None:
    args = parse_args()
    chapter_url = args.manga_url
    manga_slug = slugify_name(args.manga_name)
    allowed_exts = parse_formats_arg(args.formats)
    allowed_tokens = []
    for t in (args.formats or "").split(","):
        tt = t.strip().lower()
        if tt in {"jpg", "jpeg", "png", "webp"} and tt not in allowed_tokens:
            allowed_tokens.append(tt)
    logger = RunLogger(
        component="scraper",
        run_type="rename" if args.rename_only else "scrape",
        manga_slug=manga_slug,
        manga_name=args.manga_name,
        start_url=args.start_url,
        chapter_count=args.chapters,
        chapter_range=None,
        allowed_formats=allowed_tokens or ["jpg"],
    )
    logger.resume_enabled = bool(getattr(args, "resume", False))
    logger._write()

    global CURRENT_LOGGER
    CURRENT_LOGGER = logger

    try:
        signal.signal(signal.SIGINT, _signal_handler)
    except Exception:
        pass
    try:
        sigterm = getattr(signal, "SIGTERM", None)
        if sigterm is not None:
            signal.signal(sigterm, _signal_handler)
    except Exception:
        pass

    try:
        if args.rename_only:
            if args.chapters and args.start_url:
                start = 1
                for i in range(args.chapters):
                    next_num = start + i
                    target_url = increment_chapter_url(args.start_url, next_num)
                    chapter_number = derive_chapter_number(target_url)
                    renamed = rename_chapter_files_count(manga_slug, chapter_number)
                    logger.add_files_written(renamed)
                output_dir = build_output_directory(manga_slug, derive_chapter_number(args.start_url))
                logger.finish("success")
            else:
                chapter_number = derive_chapter_number(chapter_url)
                renamed = rename_chapter_files_count(manga_slug, chapter_number)
                logger.add_files_written(renamed)
                output_dir = build_output_directory(manga_slug, chapter_number)
                logger.finish("success")
        elif args.chapters and args.start_url:
            output_dir = ""
            start = 1
            start_num = derive_chapter_number(args.start_url)
            for i in range(args.chapters):
                next_num = start + i
                target_url = increment_chapter_url(args.start_url, next_num)
                chapter_number = derive_chapter_number(target_url)
                chapter_int: Optional[int] = None
                try:
                    chapter_int = int(chapter_number)
                except Exception:
                    chapter_int = None

                if args.resume and is_chapter_complete(manga_slug, chapter_number):
                    if chapter_int is not None:
                        logger.skipped_chapters.append(chapter_int)
                        logger.last_completed_chapter = chapter_int
                        logger._write()
                    continue

                output_dir = scrape_chapter(target_url, manga_slug, allowed_exts, logger, resume=args.resume)
                if chapter_int is not None:
                    logger.downloaded_chapters.append(chapter_int)
                    logger.last_completed_chapter = chapter_int
                    logger._write()
            try:
                s = int(start_num)
                e = s + args.chapters - 1
                logger.chapter_range = f"{s}-{e}"
            except Exception:
                logger.chapter_range = None
            logger.finish("success")
        else:
            chapter_number = derive_chapter_number(chapter_url)
            chapter_int: Optional[int] = None
            try:
                chapter_int = int(chapter_number)
            except Exception:
                chapter_int = None

            if args.resume and is_chapter_complete(manga_slug, chapter_number):
                if chapter_int is not None:
                    logger.skipped_chapters.append(chapter_int)
                    logger.last_completed_chapter = chapter_int
                    logger._write()
                output_dir = build_output_directory(manga_slug, chapter_number)
                logger.finish("success")
            else:
                output_dir = scrape_chapter(chapter_url, manga_slug, allowed_exts, logger, resume=args.resume)
                if chapter_int is not None:
                    logger.downloaded_chapters.append(chapter_int)
                    logger.last_completed_chapter = chapter_int
                    logger._write()
                logger.finish("success")
    except KeyboardInterrupt:
        logger.mark_interrupted("Interrupted by user")
        raise SystemExit(130)
    except DownloadError as exc:
        logger.fail(str(exc))
        raise SystemExit(f"Download error while scraping chapter: {exc}") from exc
    except Exception as exc:
        logger.fail(str(exc))
        raise SystemExit(f"Unexpected error while scraping chapter: {exc}") from exc
    finally:
        CURRENT_LOGGER = None

    sys.stdout.write(f"Images saved under: {output_dir}{os.linesep}")
    if args.run_indexer:
        logger.set_indexer_triggered(True)
        trigger_indexer_subprocess()


if __name__ == "__main__":
    main()
