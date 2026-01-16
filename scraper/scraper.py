# Command line scraper for downloading a single manga chapter's images.

import argparse
import os
import re
import sys
import signal
from typing import List, Set, Optional, Tuple
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
        "-mu",
        required=True,
        help="URL of the manga chapter page to scrape.",
    )
    parser.add_argument(
        "--manga-name",
        "-mn",
        required=True,
        help="Human readable manga name (used for storage slug and logs).",
    )
    parser.add_argument(
        "--formats",
        "-f",
        default="jpg",
        help="Comma-separated list of allowed image formats (e.g., jpg,png,webp). Default: jpg",
    )
    parser.add_argument(
        "--start-url",
        "-su",
        help="Starting chapter URL for multi-chapter scraping.",
    )
    parser.add_argument(
        "--chapters",
        "-c",
        type=int,
        help="Number of chapters to scrape starting from --start-url (auto-increment).",
    )
    parser.add_argument(
        "--img-class",
        "-class",
        dest="img_class",
        help="Download only images with the specified HTML class attribute.",
    )
    parser.add_argument(
        "--resume",
        "-r",
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


def extract_image_urls(html: str, base_url: str, required_class: Optional[str]) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    for img in soup.find_all("img"):
        if required_class:
            classes = img.get("class")
            if not classes:
                # allow string form too
                cls_str = img.get("class", "")
                if not cls_str:
                    continue
            match = False
            if isinstance(classes, list):
                match = required_class in [c.strip() for c in classes if c]
            else:
                try:
                    tokens = str(classes).split()
                    match = required_class in tokens
                except Exception:
                    match = False
            if not match:
                continue
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


def determine_padded_filename(index: int, total: int, image_url: str) -> str:
    width = max(3, len(str(total)))
    parsed = urlparse(image_url)
    _, ext = os.path.splitext(parsed.path)
    if not ext:
        ext = ".jpg"
    return f"{str(index).zfill(width)}{ext}"


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


def scrape_chapter(chapter_url: str, manga_slug: str, allowed_exts: Set[str], logger: RunLogger, resume: bool = False, required_class: Optional[str] = None) -> Tuple[str, int]:
    html = fetch_html(chapter_url)

    image_urls = extract_image_urls(html, chapter_url, required_class)
    if not image_urls:
        raise RuntimeError("No image URLs were found on the provided page.")

    chapter_number = derive_chapter_number(chapter_url)
    output_dir = build_output_directory(manga_slug, chapter_number)
    os.makedirs(output_dir, exist_ok=True)

    image_urls = filter_by_formats(image_urls, allowed_exts)
    total = len(image_urls)
    logger.update_stats(manga=1, chapters=1, pages=total)
    written = 0
    for index, image_url in enumerate(image_urls, start=1):
        final_name = determine_padded_filename(index, total, image_url)
        destination_path = os.path.join(output_dir, final_name)
        if resume and os.path.exists(destination_path):
            continue
        download_image(image_url, destination_path)
        written += 1
        logger.add_files_written(1)

    return output_dir, written


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
        run_type="scrape",
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
        if args.chapters and args.start_url:
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

                output_dir, wrote = scrape_chapter(target_url, manga_slug, allowed_exts, logger, resume=args.resume, required_class=getattr(args, "img_class", None))
                if chapter_int is not None and wrote > 0:
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
                output_dir, wrote = scrape_chapter(chapter_url, manga_slug, allowed_exts, logger, resume=args.resume, required_class=getattr(args, "img_class", None))
                if chapter_int is not None and wrote > 0:
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


if __name__ == "__main__":
    main()
