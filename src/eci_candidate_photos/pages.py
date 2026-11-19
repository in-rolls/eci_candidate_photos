"""Fetch each constituency's candidate page for one election.

ECI takes an election's results pages down some months after counting, so the
pages come from the Wayback Machine: the latest snapshot with status 200 of
each `candidateswise-<state><seat>.htm`, fetched raw (`id_`) so the archive
adds nothing. Each page also has a Hindi copy under /hi/ with the same photos
and votes; it is used only where no English snapshot works, which matters for
November 2023, when the archive caught 237 English pages of 678. The pages
are kept, byte for byte, in data/raw/pages/<election>.tar.gz and listed with
their snapshot and SHA-256 in data/raw/pages/<election>.csv. A rerun unpacks
the archive to data/build/pages/<election>/, fetches only pages not yet saved
and packs the archive again.

    python -m eci_candidate_photos.pages 2024_lok_sabha
"""

import re
import sys
import tarfile
from urllib.parse import urlencode

import pandas as pd
import requests

from eci_candidate_photos.common import (
    BUILD,
    RAW_PAGES,
    election,
    get,
    now,
    pack_pages,
    page_archive,
    sha256,
)

CDX = "https://web.archive.org/cdx/search/cdx"
PAGE = re.compile(r"candidateswise-([SU]\d{2})(\d+)\.htm$")


def snapshots(folder):
    """Every 200 snapshot of every candidate page in an election folder, English
    copies first and the latest first within each language."""
    params = {
        "url": f"results.eci.gov.in/{folder}/",
        "matchType": "prefix",
        "fl": "original,timestamp,statuscode",
        "filter": "statuscode:200",
        "output": "json",
    }
    response = get(f"{CDX}?{urlencode(params)}", timeout=180)
    response.raise_for_status()
    rows = response.json()[1:]
    table = pd.DataFrame(rows, columns=["original", "timestamp", "status"])
    path = (
        rf"results\.eci\.gov\.in(?::80)?/{folder}/(hi/)?(candidateswise-[^/?#]+\.htm)$"
    )
    parts = table["original"].str.extract(path)
    table["language"] = parts[0].map({"hi/": "hi"}).fillna("en")
    table["page"] = parts[1]
    table = table[table["page"].fillna("").str.match(PAGE.pattern)]
    return table.sort_values(
        ["page", "language", "timestamp"], ascending=[True, True, False]
    ).reset_index(drop=True)


def usable(response):
    """Language of a saved candidate page, or None if the snapshot is not one."""
    if response.status_code != 200 or "cand-box" not in response.text:
        return None
    if re.search(r"(Parliamentary|Assembly) Constituency", response.text):
        return "en"
    if re.search("(विधानसभा|संसदीय) (निर्वाचन )?क्षेत्र", response.text):
        return "hi"
    return None


def main(name):
    folder = election(name)["folder"]
    out = BUILD / "pages" / name
    out.mkdir(parents=True, exist_ok=True)
    if page_archive(name).exists():
        with tarfile.open(page_archive(name)) as tar:
            tar.extractall(out.parent, filter="data")
    log_path = RAW_PAGES / f"{name}.csv"
    log = pd.read_csv(log_path) if log_path.exists() else pd.DataFrame()
    done = set(log["page"]) if len(log) else set()
    found = snapshots(folder)
    print(
        f"{name}: {found['page'].nunique()} archived candidate pages, "
        f"{len(done)} already saved"
    )
    rows = log.to_dict("records") if len(log) else []
    for page, tries in found.groupby("page", sort=True):
        if page in done:
            continue
        # A snapshot can hold an error page or the other language's content;
        # try up to three per language, English first.
        for snap in tries.groupby("language").head(3).itertuples():
            url = f"https://web.archive.org/web/{snap.timestamp}id_/{snap.original}"
            try:
                response = get(url)
            except requests.RequestException as error:
                print(f"  {page}: {error}; trying the next snapshot")
                continue
            language = usable(response)
            if language:
                break
        else:
            print(f"  {page}: no usable snapshot; skipped")
            continue
        path = out / page
        path.write_bytes(response.content)
        rows.append(
            {
                "page": page,
                "language": language,
                "wayback_timestamp": snap.timestamp,
                "eci_url": snap.original,
                "wayback_url": url,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "fetched_at_utc": now(),
            }
        )
        if len(rows) % 25 == 0:
            pd.DataFrame(rows).to_csv(log_path, index=False)
    pd.DataFrame(rows).sort_values("page").to_csv(log_path, index=False)
    pack_pages(name, out)
    print(f"{name}: {len(rows)} pages saved to {page_archive(name)}")


if __name__ == "__main__":
    main(sys.argv[1])
