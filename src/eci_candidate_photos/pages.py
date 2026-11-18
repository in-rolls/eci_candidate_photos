"""Fetch each constituency's candidate page for one election.

ECI takes an election's results pages down some months after counting, so the
pages come from the Wayback Machine: the latest snapshot with status 200 of
each `candidateswise-<state><seat>.htm`, fetched raw (`id_`) so the archive
adds nothing. Pages are saved to data/raw/pages/<election>/ and listed with
their snapshot and SHA-256 in data/raw/pages/<election>.csv. Pages already
saved are not fetched again.

    python -m eci_candidate_photos.pages 2024_lok_sabha
"""

import re
import sys
from urllib.parse import urlencode

import pandas as pd

from eci_candidate_photos.common import RAW_PAGES, election, get, now, sha256

CDX = "https://web.archive.org/cdx/search/cdx"
PAGE = re.compile(r"candidateswise-([SU]\d{2})(\d+)\.htm$")


def snapshots(folder):
    """Latest 200 snapshot of every candidate page in an election folder."""
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
    # The Hindi copy of each page sits under /hi/; keep the English one.
    english = rf"results\.eci\.gov\.in(?::80)?/{folder}/(candidateswise-[^/?#]+\.htm)$"
    table["page"] = table["original"].str.extract(english)[0]
    table = table[table["page"].fillna("").str.match(PAGE.pattern)]
    return (
        table.sort_values("timestamp")
        .drop_duplicates("page", keep="last")
        .sort_values("page")
        .reset_index(drop=True)
    )


def main(name):
    folder = election(name)["folder"]
    out = RAW_PAGES / name
    out.mkdir(parents=True, exist_ok=True)
    log_path = RAW_PAGES / f"{name}.csv"
    log = pd.read_csv(log_path) if log_path.exists() else pd.DataFrame()
    done = set(log["page"]) if len(log) else set()
    found = snapshots(folder)
    print(f"{name}: {len(found)} archived candidate pages, {len(done)} already saved")
    rows = log.to_dict("records") if len(log) else []
    for snap in found.itertuples():
        if snap.page in done:
            continue
        url = f"https://web.archive.org/web/{snap.timestamp}id_/{snap.original}"
        response = get(url)
        english = re.search(r"(Parliamentary|Assembly) Constituency", response.text)
        if response.status_code != 200 or "cand-box" not in response.text:
            print(f"  {snap.page}: HTTP {response.status_code}, no candidates; skipped")
            continue
        if not english:
            print(f"  {snap.page}: not the English page; skipped")
            continue
        path = out / snap.page
        path.write_bytes(response.content)
        rows.append(
            {
                "page": snap.page,
                "wayback_timestamp": snap.timestamp,
                "eci_url": snap.original,
                "wayback_url": url,
                "path": str(path),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "fetched_at_utc": now(),
            }
        )
        if len(rows) % 25 == 0:
            pd.DataFrame(rows).to_csv(log_path, index=False)
    pd.DataFrame(rows).sort_values("page").to_csv(log_path, index=False)
    print(f"{name}: {len(rows)} pages saved")


if __name__ == "__main__":
    main(sys.argv[1])
