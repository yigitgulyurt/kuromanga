# Configuration for the standalone manga scraper process.

import os


USER_AGENT = os.environ.get(
    "SCRAPER_USER_AGENT",
    "KuromangaScraper/1.0 (+https://example.com; contact: admin@example.com)",
)

REQUEST_TIMEOUT = float(os.environ.get("SCRAPER_REQUEST_TIMEOUT", "10"))

MAX_RETRIES = int(os.environ.get("SCRAPER_MAX_RETRIES", "3"))

BASE_STORAGE_PATH = os.environ.get(
    "SCRAPER_BASE_STORAGE_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "manga"),
)

RUN_LOGS_PATH = os.environ.get(
    "SCRAPER_RUN_LOGS_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "run_logs"),
)

