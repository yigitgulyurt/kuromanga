# Download and persistence helpers for the standalone manga scraper.

import os
from typing import Optional

import requests

from . import config


class DownloadError(Exception):
    pass


def fetch_html(url: str) -> str:
    headers = {"User-Agent": config.USER_AGENT}
    attempt = 0
    last_error: Optional[Exception] = None

    while attempt < config.MAX_RETRIES:
        attempt += 1
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=config.REQUEST_TIMEOUT,
            )
            if response.status_code != 200:
                raise DownloadError(
                    f"Unexpected status code {response.status_code} for URL: {url}"
                )
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except Exception as exc:
            last_error = exc

    raise DownloadError(f"Failed to fetch HTML after {config.MAX_RETRIES} attempts: {last_error}")


def download_image(url: str, destination_path: str) -> None:
    headers = {"User-Agent": config.USER_AGENT}
    attempt = 0
    last_error: Optional[Exception] = None

    os.makedirs(os.path.dirname(destination_path), exist_ok=True)

    while attempt < config.MAX_RETRIES:
        attempt += 1
        try:
            with requests.get(
                url,
                headers=headers,
                timeout=config.REQUEST_TIMEOUT,
                stream=True,
            ) as response:
                if response.status_code != 200:
                    raise DownloadError(
                        f"Unexpected status code {response.status_code} for image URL: {url}"
                    )
                with open(destination_path, "wb") as file_handle:
                    for chunk in response.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        file_handle.write(chunk)
            return
        except Exception as exc:
            last_error = exc

    raise DownloadError(
        f"Failed to download image after {config.MAX_RETRIES} attempts: {last_error}"
    )

