"""Check data/eci_results_join.csv by a second route that shares no code with
parse.py or join.py.

1. Pages. Each saved page is read again with lxml (parse.py uses
   BeautifulSoup), and every joined row's photo URL must sit in a box on its
   page with the same name and votes.
2. eci_results. The pinned file is read again with the csv module, and every
   joined row's six-column key must exist, appear once, and give the same
   name and votes.
3. Winners. The candidate a page marks "won" must be Position 1 in
   eci_results.
4. Names. For each joined page candidate, every eci_results candidate in the
   seat is scored with difflib (join.py uses rapidfuzz) on letters, Hindi
   names first transliterated to Latin. A pair is flagged when the joined
   candidate is not the closest name in the seat. Flagged pairs are written
   to data/build/audit_names.csv for reading; they are not failures, because
   ECI spells the same person differently on its results website and in its
   report ("K.A. PAUL" and "ANAND KILARI").

Checks 1 to 3 stop the run if any row fails.

    python -m eci_candidate_photos.audit
"""

import csv
import gzip
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher

import pandas as pd
from indic_transliteration import sanscript
from lxml import html as lxml_html

from eci_candidate_photos.common import BUILD, check, election, read_pages
from eci_candidate_photos.join import JOIN

KEY = ["State_Name", "Year", "month", "Poll_No", "Constituency_No", "Position"]


def page_boxes(text):
    """{photo URL: (name, votes, result)} for one page, via lxml."""
    tree = lxml_html.fromstring(text)
    boxes = {}
    for box in tree.xpath("//div[contains(@class, 'cand-box')]"):
        src = box.xpath(".//figure//img/@src")[0]
        divs = [
            " ".join(d.text_content().split())
            for d in box.xpath(".//div[contains(@class, 'status')]/div")
        ]
        votes = next((int(t.split()[0]) for t in divs if t[:1].isdigit()), None)
        result = next(
            (
                t
                for t in divs
                if t in ("won", "lost", "leading", "trailing", "विजयी", "हारा")
            ),
            None,
        )
        name = " ".join("".join(box.xpath(".//h5//text()")).split())
        boxes[src] = (name, votes, result in ("won", "विजयी"))
    return boxes


def letters(text):
    """Lowercase Latin letters and spaces; Devanagari transliterated first."""
    text = str(text)
    if re.search("[ऀ-ॿ]", text):
        text = sanscript.transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = re.sub(r"[^a-z ]", " ", text.lower()).split()
    return " ".join(sorted(words))


def closeness(a, b):
    return SequenceMatcher(None, letters(a), letters(b)).ratio()


def eci_rows(item):
    """{key tuple: row dict} from the pinned eci_results file, via csv."""
    rows = {}
    with gzip.open(check(item["eci_results"]), "rt", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = tuple(
                str(int(float(row[k]))) if k != "State_Name" else row[k] for k in KEY
            )
            rows[key] = row
    return rows


def main():
    join = pd.read_csv(JOIN, low_memory=False)
    failures, flagged = [], []
    for name, rows in join.groupby("election"):
        item = election(name)
        pages = read_pages(name)
        eci = eci_rows(item)
        boxes = {page: page_boxes(text) for page, text in pages.items()}
        keyed = rows[rows["Position"].notna()]
        keys = [
            (r.State_Name, *(str(int(getattr(r, k))) for k in KEY[1:]))
            for r in keyed.itertuples()
        ]
        dup = [k for k, n in Counter(keys).items() if n > 1]
        failures += [(name, "key appears twice", str(k)) for k in dup]
        by_seat = defaultdict(list)
        for key, row in eci.items():
            by_seat[key[:5]].append(row)
        for r, key in zip(keyed.itertuples(), keys):
            box = boxes[r.page].get(r.photo_url)
            votes = None if pd.isna(r.votes) else int(r.votes)
            # Whitespace inside a name ("YENUMULA  KESAVA REDDY") is not compared.
            same_name = box and box[0] == " ".join(str(r.candidate).split())
            if not same_name or box[1] != votes:
                failures.append((name, "page box differs", f"{r.page} {r.candidate}"))
            row = eci.get(key)
            if row is None or row["Candidate"] != r.eci_results_candidate:
                failures.append((name, "eci_results row differs", str(key)))
                continue
            if box and box[2] and key[5] != "1":
                failures.append((name, "page winner not Position 1", str(key)))
            seat = [c for c in by_seat[key[:5]] if c["Party"] != "NOTA"]
            scores = {
                c["Candidate"]: closeness(r.candidate, c["Candidate"]) for c in seat
            }
            best = max(scores, key=scores.get)
            if (
                best != r.eci_results_candidate
                and scores[best] > scores[r.eci_results_candidate]
            ):
                flagged.append(
                    {
                        "election": name,
                        "page": r.page,
                        "language": r.language,
                        "candidate": r.candidate,
                        "votes": r.votes,
                        "joined_to": r.eci_results_candidate,
                        "joined_votes": r.eci_results_votes,
                        "joined_closeness": round(scores[r.eci_results_candidate], 2),
                        "closest_name": best,
                        "closest_closeness": round(scores[best], 2),
                        "join_basis": r.join_basis,
                    }
                )
        n_flag = sum(f["election"] == name for f in flagged)
        print(
            f"{name}: {len(rows)} rows checked, {n_flag} not joined to the closest name"
        )
    BUILD.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(flagged).to_csv(BUILD / "audit_names.csv", index=False)
    if failures:
        pd.DataFrame(failures, columns=["election", "check", "detail"]).to_csv(
            BUILD / "audit_failures.csv", index=False
        )
        raise SystemExit(f"{len(failures)} failures: {BUILD}/audit_failures.csv")
    print(
        "pages, eci_results and winners agree on every row; "
        f"names: {BUILD}/audit_names.csv"
    )


if __name__ == "__main__":
    main()
