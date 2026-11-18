"""Paths, the pinned sources and one polite HTTP session shared by every step."""

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

SOURCE = Path("data/source.json")
RAW_PAGES = Path("data/raw/pages")
PHOTOS = Path("photos")
BUILD = Path("data/build")
# One request per second: ECI and the Wayback Machine are public services.
PAUSE = 1.0
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research data collection)"}


def source():
    return json.loads(SOURCE.read_text())


def election(name):
    return source()["elections"][name]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_session = requests.Session()
_session.headers.update(HEADERS)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30), reraise=True)
def _get(url, timeout):
    response = _session.get(url, timeout=timeout)
    # 404 and 403 are answers, not transient failures; anything 5xx is retried.
    if response.status_code >= 500:
        response.raise_for_status()
    return response


def get(url, timeout=60):
    """GET with retries on server errors, then a pause before the next request."""
    try:
        return _get(url, timeout)
    finally:
        time.sleep(PAUSE)


def check(item):
    """The pinned file at item['path'], downloaded if missing.

    Stops if its SHA-256 differs from data/source.json."""
    path = Path(item["path"])
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        response = get(item["url"])
        response.raise_for_status()
        path.write_bytes(response.content)
    if sha256(path) != item["sha256"]:
        raise SystemExit(f"{path}: SHA-256 differs from data/source.json")
    return path
