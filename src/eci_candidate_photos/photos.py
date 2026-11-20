"""Download each joined candidate's photo, byte for byte as served.

The photo is fetched from ECI's own URL; where that fails, from the Wayback
Machine's raw copy of the same URL. Files go to photos/<election>/ under ECI's
file name and are listed in data/manifest.csv with where they came from, their
SHA-256, size and pixel dimensions. A photo already saved with a matching hash
is not fetched again, so the step can be stopped and rerun.

    python -m eci_candidate_photos.photos 2024_lok_sabha
"""

import sys
from pathlib import Path

import pandas as pd
import requests
from PIL import Image

from eci_candidate_photos.common import PHOTOS, get, now, sha256
from eci_candidate_photos.join import JOIN

MANIFEST = Path("data/manifest.csv")


def attempt(url, timeout):
    """(JPEG bytes or None, what happened). A host that times out (ECI's
    encore.eci.gov.in, which serves Karanpur's photos, stopped answering in
    November 2026) is an answer for this photo, not a reason to stop the run."""
    try:
        response = get(url, timeout=timeout)
    except requests.RequestException as error:
        return None, type(error).__name__
    if response.status_code == 200 and response.content[:3] == b"\xff\xd8\xff":
        return response.content, "ok"
    return None, f"HTTP {response.status_code}"


def fetch(url):
    """(bytes, where) from ECI, else from the Wayback Machine; (None, reason)."""
    content, eci = attempt(url, 30)
    if content:
        return content, "eci"
    content, wayback = attempt(f"https://web.archive.org/web/2026id_/{url}", 60)
    if content:
        return content, "wayback"
    return None, f"eci {eci}, wayback {wayback}"


def main(name):
    join = pd.read_csv(JOIN, low_memory=False)
    join = join[join["election"] == name]
    manifest = pd.read_csv(MANIFEST) if MANIFEST.exists() else pd.DataFrame()
    done = (
        set(
            manifest.loc[
                (manifest["status"] == "ok") & (manifest["election"] == name),
                "photo_url",
            ]
        )
        if len(manifest)
        else set()
    )
    rows = manifest.to_dict("records") if len(manifest) else []
    out = PHOTOS / name
    out.mkdir(parents=True, exist_ok=True)
    todo = join[~join["photo_url"].isin(done)].drop_duplicates("photo_url")
    print(f"{name}: {len(todo)} photos to fetch, {len(done)} already saved")
    todo_urls = set(todo["photo_url"])
    rows = [
        r for r in rows if not (r["election"] == name and r["photo_url"] in todo_urls)
    ]
    for i, item in enumerate(todo.itertuples(), start=1):
        path = out / item.photo_url.rsplit("/", 1)[1]
        content, where = fetch(item.photo_url)
        row = {"election": name, "photo_url": item.photo_url, "fetched_at_utc": now()}
        if content is None:
            row.update(status="fetch_failed", source=where)
        else:
            path.write_bytes(content)
            with Image.open(path) as image:
                width, height = image.size
            row.update(
                status="ok",
                source=where,
                path=str(path),
                sha256=sha256(path),
                bytes=len(content),
                width=width,
                height=height,
            )
        rows.append(row)
        if i % 100 == 0:
            pd.DataFrame(rows).to_csv(MANIFEST, index=False)
            print(f"  {i} of {len(todo)}")
    table = pd.DataFrame(rows).sort_values(["election", "photo_url"])
    table.to_csv(MANIFEST, index=False)
    mine = table[table["election"] == name]
    print(f"{name}: {mine['status'].value_counts().to_dict()}")


if __name__ == "__main__":
    main(sys.argv[1])
