# ECI Candidate Photos

Photographs of 36,122 candidates in India's 2024 Lok Sabha election and in every
state assembly election from November 2023 to May 2026, as the Election
Commission of India (ECI) showed them on its results website. Each photo is
matched to the candidate's row in
[in-rolls/eci_results](https://github.com/in-rolls/eci_results). Candidates
submit the photograph with their nomination papers, and since 2015 ECI has
printed it next to their name on the ballot.

- [`photos/<election>/`](photos/): one JPEG per candidate, under ECI's file
  name, byte for byte as ECI served it. The photos take 1.8 GB; the median is
  27 KB and 356 by 450 pixels.
- [`data/eci_results_join.csv`](data/eci_results_join.csv): one row per
  candidate, with the candidate's key in eci_results and the photo's path.
- [`data/coverage.csv`](data/coverage.csv): seats and candidates, with and
  without a photo, by election and state.
- [`data/manifest.csv`](data/manifest.csv): each photo's URL, source, retrieval
  time, SHA-256, size in bytes and pixel dimensions.

A fixed copy is on Zenodo,
[doi:10.5281/zenodo.24395870](https://doi.org/10.5281/zenodo.24395870), with
the photos in one zip per election. That DOI always resolves to the latest
version; version v2026.11 (commit 3f9ddb2) is
[doi:10.5281/zenodo.24395871](https://doi.org/10.5281/zenodo.24395871).

## Coverage

| Election | States | Candidates with a photo |
|---|---|---|
| Lok Sabha, 2024 | all | 8,359 of 8,359 |
| Assemblies, Nov 2023 | Chhattisgarh, Madhya Pradesh, Mizoram, Rajasthan, Telangana | 4,388 of 8,042 |
| Karanpur by-poll, Jan 2024 | Rajasthan | 0 of 12 |
| Assemblies, Jun 2024 | Andhra Pradesh, Arunachal Pradesh, Odisha, Sikkim | 3,961 of 3,961 |
| Assemblies, Oct 2024 | Haryana, Jammu and Kashmir | 1,904 of 1,904 |
| Assemblies, Nov 2024 | Jharkhand, Maharashtra | 5,347 of 5,347 |
| Delhi, Feb 2025 | Delhi | 699 of 699 |
| Bihar, Nov 2025 | Bihar | 2,616 of 2,616 |
| Assemblies, May 2026 | Assam, Kerala, Puducherry, Tamil Nadu, West Bengal | 8,848 of 8,848 |

The gaps have two causes. The Internet Archive saved only 372 of the 678 seat
pages for November 2023, and a candidate's photo can be found only through
their seat's page. The seats it missed are spread unevenly: Madhya Pradesh has
202 of 230, Chhattisgarh 16 of 90 and Mizoram 2 of 40. Karanpur's photos sit on
a different ECI server, encore.eci.gov.in, which stopped accepting connections
in November 2026 and which the Archive did not copy; its 12 candidates are
matched, and `make photos ELECTION=2024_01_karanpur` will fetch them if the
server returns.

## Use with eci_results

eci_results identifies a candidate by six columns: `State_Name`, `Year`,
`month`, `Poll_No`, `Constituency_No` and `Position`. The join file carries all
six, so a merge on them attaches a photo to each candidate. The name alone will
not do: 16 pairs of candidates in 15 Lok Sabha seats share a name.

```python
import pandas as pd

url = "https://raw.githubusercontent.com/in-rolls/eci_results/main/data/release/"
results = pd.read_csv(url + "GE_2024.csv.gz", low_memory=False)
photos = pd.read_csv("data/eci_results_join.csv", low_memory=False)

key = ["State_Name", "Year", "month", "Poll_No", "Constituency_No", "Position"]
results = results.merge(photos[key + ["photo_path"]], on=key, how="left")

results[results.Candidate == "CHANDESHWAR PRASAD"][["Party", "Votes", "photo_path"]]
# JD(U)  300444  photos/2024_lok_sabha/CHAND-2024-11849.jpg
# IND      5378  photos/2024_lok_sabha/CHAND-2024-12793.jpg
```

The assemblies work the same way with `AE_2023_2026.csv.gz`. NOTA rows get no
photo. The join file also lists Mukeshkumar Dalal, elected unopposed in Surat
in 2024; eci_results leaves that seat out, so his key columns are empty.

## How the photos were collected

ECI takes an election's results pages down some months after counting, so each
seat's candidate page comes from its latest snapshot in the Internet Archive's
Wayback Machine. Where no English snapshot exists, the Hindi one is used: 159
of the November 2023 pages are in Hindi, with names in Devanagari. A page gives
each candidate's name, party, votes and the URL of the photo. The pages for
each election are stored as one compressed archive under
[`data/raw/pages/`](data/raw/pages/), with each page's snapshot time and
SHA-256 in the CSV beside it.

The photos themselves are still on ECI's server, and 36,114 came from there.
Seven that ECI refused at the moment of asking came from the Wayback Machine's
copy of the same URL. Requests go out one per second.

## How candidates are matched

A seat's page candidates are paired with its eci_results candidates by
minimizing, over all pairings, the sum of two costs: the gap between the two
vote counts as a share of the larger, and one minus the similarity of the two
names (letters only, Devanagari first transliterated to Latin). Where the page
shows ECI's final count, the votes decide and names only break ties. Where the
archived page caught the count before it ended, as for four seats in Bihar and
Madhya Pradesh, the names decide. `join_basis` is `votes` when the count is
equal and unique in the seat on both sides, which covers 35,362 candidates, and
`votes and name` for the other 772. The build stops if any candidate on either
side is left unmatched.

Votes alone can mislead. In Tirupati in 2024 the archived page gave RAVILLA
MANJULA 105 votes and the final report gave 105 to L N Lakshmi. Names alone can
too: B. SATHISH KUMAR and SATHISH.B ran in one Tamil Nadu seat in 2026 with 19
votes each. ECI's file names often abbreviate or misspell the candidate's name,
so they play no part in the match.

## Audit

`make audit` checks the join by a second route that shares no code with it. It
reads the saved pages again with a different HTML parser and eci_results with
Python's csv module, then requires three things of every row: the photo,
name and votes match a box on the page; the key exists once in eci_results with
the same name and votes; and the candidate a page marks as the winner is
Position 1. All 36,135 rows pass. The audit caught two errors in an earlier
version of the match, both since fixed: tied candidates on Hindi pages paired
at random, and the two Sathish namesakes crossed.

The audit also lists 63 pairs whose eci_results name is not the closest name in
the seat (`data/build/audit_names.csv`). Each was read: 59 are one person
spelled two ways on a unique vote count ("K.A. PAUL" and "ANAND KILARI", or a
name with "S/o" and the father's name added), and four sit beside a namesake
whose count matched exactly.

Seven people ran in two seats and have one photo for both: for two, ECI serves
one file to both seats' pages; for five, it serves the same image under two
file names. So the 36,122 candidates have 36,121 files.

## Rebuild

```sh
make sync
make pages ELECTION=2024_lok_sabha    # archived pages, about 10 minutes
make photos ELECTION=2024_lok_sabha   # parse, join, then photos; about 2.5 hours
make audit
```

Elections are named in [`data/source.json`](data/source.json), with the pinned
eci_results file each one is matched against. `make photos` runs the parse and
the join first and fetches nothing unless every candidate is matched. It can be
stopped and rerun; photos already in the manifest are skipped.

## License

The code is under the MIT license. The photographs were published by ECI, and
this repository claims no rights in them.
