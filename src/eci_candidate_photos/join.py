"""Join each page candidate to its row in in-rolls/eci_results.

First pass: within a constituency a vote count is almost always unique, so
candidates are joined on state, constituency number and votes, and the name is
only compared as a check (pairs whose names share no word are reported).
Second pass: candidates left over (tied votes, or an archived page whose counts
differ slightly from ECI's final report) are joined by name, letters only,
within the constituency. `join_basis` records which pass matched each row.

Writes data/eci_results_join.csv and stops if any eci_results candidate or
page candidate is left unmatched.

    python -m eci_candidate_photos.join 2024_lok_sabha
"""

import re
import sys
from pathlib import Path

import pandas as pd

from eci_candidate_photos.common import BUILD, check, election

JOIN = Path("data/eci_results_join.csv")


def state_key(text):
    text = str(text).upper().replace("&", " AND ")
    return re.sub(r"^NCTOF", "", re.sub(r"[^A-Z]", "", text))


def name_key(text):
    return re.sub(r"[^A-Z]", "", str(text).upper())


def words(text):
    return set(re.findall(r"[A-Z]{2,}", str(text).upper()))


def main(name):
    item = election(name)
    results = pd.read_csv(check(item["eci_results"]), low_memory=False)
    results = results[results["Party"] != "NOTA"].reset_index(names="eci_results_row")
    page = pd.read_csv(BUILD / f"candidates_{name}.csv")
    page = page[~page["nota"]].copy()
    for frame, col in ((results, "State_Name"), (page, "state_eci")):
        frame["state_key"] = frame[col].map(state_key)
    results = results.rename(columns={"Constituency_No": "constituency_no"})
    results["votes"] = results["Votes"]
    for frame, col in ((results, "Candidate"), (page, "candidate")):
        frame["name_key"] = frame[col].map(name_key)
    seat = ["state_key", "constituency_no"]
    keep = ["eci_results_row", "Candidate", "Party"]
    # Pass 1: votes, where a count is unique within its constituency on both sides.
    key = seat + ["votes"]
    unique_page = ~page.duplicated(key, keep=False) & page["votes"].notna()
    unique_results = ~results.duplicated(key, keep=False)
    first = page[unique_page].merge(results[unique_results][key + keep], on=key)
    first["join_basis"] = "votes"
    # Pass 2: the rest by name within the constituency. The archived page can
    # show a slightly different count from ECI's final report.
    matched = set(zip(first["page"], first["order_on_page"]))
    rest_page = page[
        [(a, b) not in matched for a, b in zip(page["page"], page["order_on_page"])]
    ]
    rest_results = results[~results["eci_results_row"].isin(first["eci_results_row"])]
    second = rest_page.merge(
        rest_results[seat + ["name_key", "votes"] + keep].rename(
            columns={"votes": "eci_results_votes"}
        ),
        on=seat + ["name_key"],
        how="outer",
        indicator=True,
    )
    second.loc[second["_merge"] == "both", "join_basis"] = "name"
    first["_merge"] = "both"
    first["eci_results_votes"] = first["votes"]
    joined = pd.concat([first, second], ignore_index=True)
    both = joined["_merge"] == "both"
    joined["name_overlap"] = [
        bool(words(a) & words(b)) if ok else None
        for a, b, ok in zip(joined["candidate"], joined["Candidate"], both)
    ]
    # Candidates the source lists but eci_results cannot have, with the reason.
    known = {e["page"]: e["reason"] for e in item.get("not_in_eci_results", [])}
    excused = (joined["_merge"] == "left_only") & joined["page"].isin(known)
    joined.loc[excused, "join_basis"] = "not_in_eci_results"
    both = (joined["_merge"] == "both") | excused
    only_page = joined[(joined["_merge"] == "left_only") & ~excused]
    only_results = joined[joined["_merge"] == "right_only"]
    print(
        f"{name}: {both.sum()} joined, {len(only_page)} only on pages, "
        f"{len(only_results)} only in eci_results, "
        f"{joined['name_overlap'].eq(False).sum()} joined pairs share no name word"
    )
    cols = [
        "election",
        "page",
        "order_on_page",
        "state_eci",
        "constituency_no",
        "candidate",
        "party",
        "votes",
        "eci_results_votes",
        "join_basis",
        "eci_results_row",
        "Candidate",
        "Party",
        "name_overlap",
        "photo_url",
    ]
    out = joined[both][cols].rename(
        columns={"Candidate": "eci_results_candidate", "Party": "eci_results_party"}
    )
    out["eci_results_row"] = out["eci_results_row"].astype("Int64")
    previous = pd.read_csv(JOIN) if JOIN.exists() else pd.DataFrame(columns=cols)
    previous = previous[previous["election"] != name]
    pd.concat([previous, out]).sort_values(
        ["election", "page", "order_on_page"]
    ).to_csv(JOIN, index=False)
    if len(only_page) or len(only_results):
        BUILD.mkdir(parents=True, exist_ok=True)
        joined[~both].to_csv(BUILD / f"unjoined_{name}.csv", index=False)
        raise SystemExit(f"unjoined rows written to {BUILD}/unjoined_{name}.csv")


if __name__ == "__main__":
    main(sys.argv[1])
