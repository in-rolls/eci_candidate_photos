"""Read the candidates off each saved page: name, party, result, votes, photo.

Each candidate is a `cand-box`: a <figure> with the photo, a status block with
the result and votes, and the name (<h5>) and party (<h6>). The page heading
gives the constituency number, name and state. The NOTA box (img/nota.jpg) is
kept as a row so the page reconciles with the results file, but has no photo.

    python -m eci_candidate_photos.parse 2024_lok_sabha
"""

import re
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from eci_candidate_photos.common import BUILD, RAW_PAGES

# "9 - Bapatla (SC) (Andhra Pradesh)": the state is the last parenthesis.
HEADING = re.compile(r"^\s*(\d+)\s*-\s*(.+?)\s*\(([^()]+)\)\s*$")


def parse_page(html):
    """(constituency number, name, state, list of candidate dicts)."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h2").find("span").get_text(" ", strip=True)
    number, seat, state = HEADING.match(heading).groups()
    rows = []
    for order, box in enumerate(soup.select("div.cand-box"), start=1):
        src = box.find("figure").find("img")["src"]
        status = box.select_one("div.status")
        lines = [d.get_text(" ", strip=True) for d in status.find_all("div")]
        votes = next(
            (int(m[1]) for t in lines if (m := re.match(r"^(\d+)\b", t))), None
        )
        name, party = box.find("h5"), box.find("h6")
        nota = src.endswith("nota.jpg")
        rows.append(
            {
                "order_on_page": order,
                "candidate": name.get_text(strip=True) if name else None,
                "party": party.get_text(strip=True) if party else None,
                "result": next((t for t in lines if t in ("won", "lost")), None),
                "votes": votes,
                "nota": nota,
                "photo_url": None if nota else src,
            }
        )
    return int(number), seat, state, rows


def main(name):
    log = pd.read_csv(RAW_PAGES / f"{name}.csv")
    frames = []
    for item in log.itertuples():
        number, seat, state, rows = parse_page(Path(item.path).read_text("utf-8"))
        frames.append(
            pd.DataFrame(rows).assign(
                election=name,
                page=item.page,
                state_eci=state,
                constituency_no=number,
                constituency_name=seat,
            )
        )
    table = pd.concat(frames, ignore_index=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / f"candidates_{name}.csv"
    table.to_csv(out, index=False)
    named = table[~table["nota"]]
    print(
        f"{out}: {table['page'].nunique()} pages, {len(named)} candidates, "
        f"{named['photo_url'].isna().sum()} without a photo URL, "
        f"{named['votes'].isna().sum()} without votes"
    )


if __name__ == "__main__":
    main(sys.argv[1])
