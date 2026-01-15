# Command line scraper for downloading a single manga chapter's images.

import argparse
import os
import re
import sys
from typing import List
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from . import config
from .downloader import DownloadError, download_image, fetch_html
from .logger import RunLogger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download manga chapter images from a given URL.",
    )
    parser.add_argument(
        "--manga-url",
        required=True,
        help="URL of the manga chapter page to scrape.",
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


def determine_filename(index: int, total: int, image_url: str) -> str:
    width = max(3, len(str(total)))
    parsed = urlparse(image_url)
    _, ext = os.path.splitext(parsed.path)
    if not ext:
        ext = ".jpg"
    padded_index = str(index).zfill(width)
    return f"{padded_index}{ext}"


def scrape_chapter(chapter_url: str, logger: RunLogger) -> str:
    html = fetch_html(chapter_url)

    image_urls = extract_image_urls(html, chapter_url)
    if not image_urls:
        raise RuntimeError("No image URLs were found on the provided page.")

    manga_slug = derive_manga_slug(chapter_url)
    chapter_number = derive_chapter_number(chapter_url)
    output_dir = build_output_directory(manga_slug, chapter_number)

    total = len(image_urls)
    logger.update_stats(manga=1, chapters=1, pages=total)

    for index, image_url in enumerate(image_urls, start=1):
        filename = determine_filename(index, total, image_url)
        destination_path = os.path.join(output_dir, filename)
        download_image(image_url, destination_path)

    return output_dir


def main() -> None:
    args = parse_args()
    chapter_url = args.manga_url
    logger = RunLogger("scraper")

    try:
        output_dir = scrape_chapter(chapter_url, logger)
        logger.finish()
    except DownloadError as exc:
        logger.fail(str(exc))
        raise SystemExit(f"Download error while scraping chapter: {exc}") from exc
    except Exception as exc:
        logger.fail(str(exc))
        raise SystemExit(f"Unexpected error while scraping chapter: {exc}") from exc

    sys.stdout.write(f"Images saved under: {output_dir}{os.linesep}")


if __name__ == "__main__":
    main()

