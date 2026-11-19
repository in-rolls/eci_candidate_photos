"""Join each page candidate to its row in in-rolls/eci_results.

The election's rows are taken from eci_results by `select` in
data/source.json (Year and month), general polls only (Poll_No 0), NOTA
dropped. Candidates are joined within the seat (state and constituency
number) in two passes:

1. Votes. Within a seat a vote count is almost always unique, so a candidate
   whose count is unique on both sides is joined on it.
2. Name, letters only, for the rest: candidates with tied counts, and seats
   where the archived page caught a count slightly different from ECI's final
   report. Hindi pages print names in Devanagari, which are transliterated.

`join_basis` records the pass. Pairs whose two names share no word are counted
as a check; on Hindi pages the check does not apply.

A seat with no archived page has no photos; data/coverage.csv counts seats and
candidates with and without a page, by election and state. The build stops if
any candidate is left unmatched in a seat that has a page, or if a page has no
seat in eci_results and data/source.json gives no reason.

Each row carries eci_results' own key for the candidate: State_Name, Year,
month, Poll_No, Constituency_No and Position, which are unique in eci_results.
The name is not a key, because namesakes share a seat (16 pairs in the 2024 Lok
Sabha).

    python -m eci_candidate_photos.join 2024_lok_sabha
"""

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from indic_transliteration import sanscript
from rapidfuzz import fuzz
from scipy.optimize import linear_sum_assignment

from eci_candidate_photos.common import BUILD, PHOTOS, check, election

JOIN = Path("data/eci_results_join.csv")
COVERAGE = Path("data/coverage.csv")
RESULTS_KEY = ["State_Name", "Year", "month", "Poll_No", "Constituency_No", "Position"]
SEAT = ["state_key", "constituency_no"]
COLUMNS = [
    "election",
    "page",
    "language",
    "order_on_page",
    "state_eci",
    "constituency_no",
    "candidate",
    "party",
    "votes",
    "eci_results_votes",
    "join_basis",
    "vote_gap",
    "name_similarity",
    *RESULTS_KEY,
    "eci_results_candidate",
    "eci_results_party",
    "name_overlap",
    "photo_url",
    "photo_path",
]


def state_key(text):
    text = str(text).upper().replace("&", " AND ")
    return re.sub(r"^NCTOF", "", re.sub(r"[^A-Z]", "", text))


def name_key(text):
    return re.sub(r"[^A-Z]", "", str(text).upper())


def words(text):
    return set(re.findall(r"[A-Z]{2,}", str(text).upper()))


def load_results(item):
    results = pd.read_csv(check(item["eci_results"]), low_memory=False)
    for col, value in item["eci_results"]["select"].items():
        results = results[
            results[col].isin(value if isinstance(value, list) else [value])
        ]
    results = results[(results["Poll_No"] == 0) & (results["Party"] != "NOTA")]
    results = results.rename(
        columns={
            "Candidate": "eci_results_candidate",
            "Party": "eci_results_party",
            "Votes": "eci_results_votes",
        }
    )
    results["state_key"] = results["State_Name"].map(state_key)
    results["constituency_no"] = results["Constituency_No"]
    results["name_key"] = results["eci_results_candidate"].map(name_key)
    return results.reset_index(drop=True).reset_index(names="row")


def load_page(name):
    page = pd.read_csv(BUILD / f"candidates_{name}.csv")
    page = page[~page["nota"]].copy()
    page["state_key"] = page["state_eci"].map(state_key)
    page["name_key"] = page["candidate"].map(name_key)
    # Devanagari leaves no letters A-Z; an empty key must not match another.
    page.loc[page["name_key"] == "", "name_key"] = None
    return page


def latin(text):
    """Uppercase Latin letters and spaces. Devanagari (Hindi pages) is first
    transliterated to IAST with indic_transliteration and stripped of
    diacritics, so बलराम सिंह तौमर becomes BALARAMA SIMHA TAUMARA, close enough
    to eci_results' "Balram Singh Taumar" to break a tie on votes."""
    text = str(text)
    if re.search("[\u0900-\u097f]", text):
        text = sanscript.transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z ]", " ", text.upper()).strip()


def name_similarity(a, b):
    """0 to 1: the mean of rapidfuzz's token-set and token-sort ratios on
    letters. Token-set ignores word order, initials' punctuation and an extra
    word ("ARANII SRENEVASULU" and "Aranii Srenevasulu(jmc)"), but scores a
    name 1 against any name that contains it; token-sort tells two namesakes
    apart by their other words (May 2026: "B. SATHISH KUMAR" and "SATHISH.B",
    19 votes each, in one seat)."""
    a, b = latin(a), latin(b)
    if not a or not b:
        return 0.0
    return (fuzz.token_set_ratio(a, b) + fuzz.token_sort_ratio(a, b)) / 200


def vote_gap(a, b):
    """0 for equal counts, rising to 1 as they diverge; 1 if either is missing."""
    if pd.isna(a) or pd.isna(b):
        return 1.0
    return abs(a - b) / max(a, b, 1)


def match(page, results):
    """Page rows with their eci_results row number (`row`) and `join_basis`.

    Within each seat, the pairing of page candidates to eci_results candidates
    that minimizes the summed cost, vote gap plus (1 - name similarity), solved
    exactly with scipy's linear_sum_assignment. Where every count on the page
    equals the final report's, the vote gap decides, and names only break ties.
    Where the archived page caught counts slightly off the final report, equal
    counts can belong to different people (Tirupati, 2024: the page's RAVILLA
    MANJULA has 105, as does the report's L N Lakshmi), and the names decide.
    """
    pairs = []
    page_seats = page.groupby(SEAT)
    for seat, group in results.groupby(SEAT):
        if seat not in page_seats.groups:
            continue
        mine = page_seats.get_group(seat)
        cost = [
            [
                vote_gap(p.votes, r.eci_results_votes)
                + 1
                - name_similarity(p.candidate, r.eci_results_candidate)
                for r in group.itertuples()
            ]
            for p in mine.itertuples()
        ]
        rows, cols = linear_sum_assignment(cost)
        for i, k in zip(rows, cols):
            p, r = mine.iloc[i], group.iloc[k]
            pairs.append(
                {
                    "index": p["index"],
                    "row": r["row"],
                    "vote_gap": vote_gap(p["votes"], r["eci_results_votes"]),
                    "name_similarity": name_similarity(
                        p["candidate"], r["eci_results_candidate"]
                    ),
                    "unique_count": (mine["votes"] == p["votes"]).sum() == 1
                    and (group["eci_results_votes"] == r["eci_results_votes"]).sum()
                    == 1,
                }
            )
    pairs = pd.DataFrame(pairs)
    exact = (pairs["vote_gap"] == 0) & pairs["unique_count"]
    pairs["join_basis"] = exact.map({True: "votes", False: "votes and name"})
    return (
        page.merge(pairs.drop(columns="unique_count"), on="index")
        .drop(columns=["name_key"])
        .merge(results.drop(columns=SEAT + ["name_key"]), on="row")
    )


def coverage(name, page, results, joined):
    seats = results.groupby("State_Name").agg(
        seats=("constituency_no", "nunique"), candidates=("row", "size")
    )
    with_page = results[results.set_index(SEAT).index.isin(page.set_index(SEAT).index)]
    seats["seats_with_page"] = with_page.groupby("State_Name")[
        "constituency_no"
    ].nunique()
    seats["candidates_joined"] = joined.groupby("State_Name").size()
    table = seats.fillna(0).astype(int).reset_index().assign(election=name)
    previous = pd.read_csv(COVERAGE) if COVERAGE.exists() else pd.DataFrame()
    previous = previous[previous.get("election") != name] if len(previous) else previous
    pd.concat([previous, table])[
        [
            "election",
            "State_Name",
            "seats",
            "seats_with_page",
            "candidates",
            "candidates_joined",
        ]
    ].sort_values(["election", "State_Name"]).to_csv(COVERAGE, index=False)
    return table


def main(name):
    item = election(name)
    results = load_results(item)
    page = load_page(name).reset_index()
    joined = match(page, results)
    joined["name_overlap"] = [
        bool(words(a) & words(b)) if lang == "en" else None
        for a, b, lang in zip(
            joined["candidate"], joined["eci_results_candidate"], joined["language"]
        )
    ]
    joined["photo_path"] = [
        f"{PHOTOS}/{name}/{url.rsplit('/', 1)[1]}" for url in joined["photo_url"]
    ]
    # Candidates the source lists but eci_results cannot have, with the reason.
    known = {e["page"]: e["reason"] for e in item.get("not_in_eci_results", [])}
    left_page = page[~page["index"].isin(joined["index"])]
    excused = left_page[left_page["page"].isin(known)].assign(
        join_basis="not_in_eci_results",
        photo_path=lambda d: [
            f"{PHOTOS}/{name}/{u.rsplit('/', 1)[1]}" for u in d["photo_url"]
        ],
    )
    left_page = left_page[~left_page["page"].isin(known)]
    paged = results.set_index(SEAT).index.isin(page.set_index(SEAT).index)
    left_results = results[paged & ~results["row"].isin(joined["row"])]
    out = pd.concat([joined, excused], ignore_index=True)[COLUMNS]
    for col in ["Year", "month", "Poll_No", "Constituency_No", "Position"]:
        out[col] = out[col].astype("Int64")
    previous = (
        pd.read_csv(JOIN, low_memory=False)
        if JOIN.exists()
        else pd.DataFrame(columns=COLUMNS)
    )
    previous = previous.reindex(columns=COLUMNS)
    previous = previous[previous["election"] != name]
    pd.concat([previous, out]).sort_values(
        ["election", "page", "order_on_page"]
    ).to_csv(JOIN, index=False)
    table = coverage(name, page, results, joined)
    basis = joined["join_basis"].value_counts().to_dict()
    seats = f"{table['seats_with_page'].sum()} of {table['seats'].sum()}"
    print(
        f"{name}: {len(joined)} joined {basis}, "
        f"{len(excused)} excused, {len(left_page)} only on pages, "
        f"{len(left_results)} only in eci_results in seats with a page, "
        f"{joined['name_overlap'].eq(False).sum()} pairs share no name word; "
        f"seats with a page {seats}, "
        f"candidates joined {table['candidates_joined'].sum()} of "
        f"{table['candidates'].sum()}"
    )
    if len(left_page) or len(left_results):
        BUILD.mkdir(parents=True, exist_ok=True)
        pd.concat(
            [left_page.assign(side="page"), left_results.assign(side="eci_results")]
        ).to_csv(BUILD / f"unjoined_{name}.csv", index=False)
        raise SystemExit(f"unjoined rows written to {BUILD}/unjoined_{name}.csv")


if __name__ == "__main__":
    main(sys.argv[1])
