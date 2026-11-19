import pandas as pd

from eci_candidate_photos.join import match


def frames(page_rows, result_rows):
    seat = {"state_key": "ANDHRAPRADESH", "constituency_no": 167}
    page = pd.DataFrame(
        [
            {**seat, "index": i, "votes": v, "candidate": n, "name_key": ""}
            for i, (v, n) in enumerate(page_rows)
        ]
    )
    results = pd.DataFrame(
        [
            {
                **seat,
                "row": i,
                "eci_results_votes": v,
                "eci_results_candidate": n,
                "name_key": "",
            }
            for i, (v, n) in enumerate(result_rows)
        ]
    )
    return page, results


def pairs(page, results):
    joined = match(page, results)
    return dict(zip(joined["candidate"], joined["eci_results_candidate"]))


def test_names_overrule_a_coincidental_equal_count():
    # Tirupati 2024: the archived page is a few votes off the final report.
    page, results = frames(
        [(107, "LAKSHMI L. N."), (105, "RAVILLA MANJULA")],
        [(105, "L N Lakshmi"), (103, "R Manjula")],
    )
    assert pairs(page, results) == {
        "LAKSHMI L. N.": "L N Lakshmi",
        "RAVILLA MANJULA": "R Manjula",
    }


def test_names_break_tied_counts():
    page, results = frames(
        [(34, "THOTA PRAKASH BABU"), (34, "M JAGADEESH")],
        [(34, "M Jagadeesh"), (34, "Thota Prakash Babu")],
    )
    joined = match(page, results)
    assert pairs(page, results)["M JAGADEESH"] == "M Jagadeesh"
    assert set(joined["join_basis"]) == {"votes and name"}


def test_unique_equal_counts_decide_when_names_say_nothing():
    page, results = frames([(900, "राम"), (40, "सीता")], [(40, "Sita"), (900, "Ram")])
    joined = match(page, results)
    assert pairs(page, results) == {"राम": "Ram", "सीता": "Sita"}
    assert set(joined["join_basis"]) == {"votes"}


def test_namesakes_with_equal_counts_keep_their_own_photos():
    page, results = frames(
        [(19, "B. SATHISH KUMAR"), (19, "SATHISH.B")],
        [(19, "Sathish.b"), (19, "B. Sathish Kumar")],
    )
    assert pairs(page, results) == {
        "B. SATHISH KUMAR": "B. Sathish Kumar",
        "SATHISH.B": "Sathish.b",
    }


def test_hindi_names_break_tied_counts():
    page, results = frames(
        [(116, "बलराम सिंह तौमर"), (116, "मनोज शुक्ला")],
        [(116, "Manoj Shukla"), (116, "Balram Singh Taumar")],
    )
    assert pairs(page, results)["बलराम सिंह तौमर"] == "Balram Singh Taumar"
