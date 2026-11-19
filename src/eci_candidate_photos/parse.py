"""Read the candidates off each saved page: name, party, result, votes, photo.

Each candidate is a `cand-box`: a <figure> with the photo, a status block with
the result and votes, and the name (<h5>) and party (<h6>). The NOTA box
(img/nota.jpg) is kept as a row so the page reconciles with the results file,
but has no photo.

The state and seat number come from the file name, `candidateswise-S1210.htm`
being state S12, seat 10, because headings differ: Hindi pages for November
2023 leave out the seat number, and Karanpur's adds "(adjourned AC)" inside
the state's parentheses. ECI's state codes are in data/state_codes.csv, read
off the 2024 Lok Sabha pages, whose English headings name the state. Where an
English heading names a state, the build stops if it disagrees with the code.

    python -m eci_candidate_photos.parse 2024_lok_sabha
"""

import re
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from eci_candidate_photos.common import BUILD, RAW_PAGES, read_pages
from eci_candidate_photos.join import state_key
from eci_candidate_photos.pages import PAGE

STATE_CODES = Path("data/state_codes.csv")
# "9 - Bapatla (SC) (Andhra Pradesh)": the state is the last parenthesis.
HEADING = re.compile(r"^\s*(\d+)\s*-\s*(.+?)\s*\(([^()]+)\)\s*$")
# A page archived before counting ended says "leading" or "trailing".
RESULT = {
    "won": "won",
    "lost": "lost",
    "leading": "leading",
    "trailing": "trailing",
    "विजयी": "won",
    "हारा": "lost",
}


def parse_page(html):
    """(heading text, list of candidate dicts)."""
    soup = BeautifulSoup(html, "html.parser")
    h2 = soup.find("h2")
    heading = (h2.find("span") or h2).get_text(" ", strip=True)
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
                "result": next((RESULT[t] for t in lines if t in RESULT), None),
                "votes": votes,
                "nota": nota,
                "photo_url": None if nota else src,
            }
        )
    return heading, rows


def main(name):
    log = pd.read_csv(RAW_PAGES / f"{name}.csv")
    states = pd.read_csv(STATE_CODES).set_index("code")["state"]
    pages = read_pages(name)
    frames = []
    for item in log.itertuples():
        heading, rows = parse_page(pages[item.page])
        code, number = PAGE.search(item.page).groups()
        state = states[code]
        named = HEADING.match(heading) if item.language == "en" else None
        if named and state_key(named[3]) != state_key(state):
            raise SystemExit(f"{item.page}: heading says {named[3]!r}, code {state}")
        frames.append(
            pd.DataFrame(rows).assign(
                election=name,
                page=item.page,
                language=item.language,
                state_eci=state,
                constituency_no=int(number),
                heading=heading,
            )
        )
    table = pd.concat(frames, ignore_index=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / f"candidates_{name}.csv"
    table.to_csv(out, index=False)
    named = table[~table["nota"]]
    print(
        f"{out}: {table['page'].nunique()} pages "
        f"({(log['language'] == 'hi').sum()} Hindi), {len(named)} candidates, "
        f"{named['photo_url'].isna().sum()} without a photo URL, "
        f"{named['votes'].isna().sum()} without votes, "
        f"{named['result'].isna().sum()} without a result"
    )


if __name__ == "__main__":
    main(sys.argv[1])
