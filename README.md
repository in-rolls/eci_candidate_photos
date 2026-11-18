# ECI Candidate Photos

Photographs of all 8,360 candidates in India's 2024 Lok Sabha election, as the
Election Commission of India (ECI) showed them on its results website, each
matched to the candidate's row in
[in-rolls/eci_results](https://github.com/in-rolls/eci_results). Candidates
submit the photograph with their nomination papers, and since 2015 ECI has
printed it next to their name on the ballot.

- [`photos/2024_lok_sabha/`](photos/2024_lok_sabha/): one JPEG per candidate,
  under ECI's file name, byte for byte as ECI served it. The folder holds
  442 MB; the median photo is 23 KB and 325 by 406 pixels.
- [`data/eci_results_join.csv`](data/eci_results_join.csv): one row per
  candidate, with the candidate's key in eci_results and the photo's path.
- [`data/manifest.csv`](data/manifest.csv): each photo's URL, retrieval time,
  SHA-256, size in bytes and pixel dimensions.

## Use with eci_results

eci_results identifies a candidate by six columns: `State_Name`, `Year`,
`month`, `Poll_No`, `Constituency_No` and `Position`. The join file carries all
six, so a merge on them attaches a photo to each candidate. The name alone will
not do: 16 pairs of candidates in 15 seats share a name.

```python
import pandas as pd

url = "https://raw.githubusercontent.com/in-rolls/eci_results/main/data/release/"
results = pd.read_csv(url + "GE_2024.csv.gz", low_memory=False)
photos = pd.read_csv("data/eci_results_join.csv")

key = ["State_Name", "Year", "month", "Poll_No", "Constituency_No", "Position"]
results = results.merge(photos[key + ["photo_path"]], on=key, how="left")

results[results.Candidate == "CHANDESHWAR PRASAD"][["Party", "Votes", "photo_path"]]
# JD(U)  300444  photos/2024_lok_sabha/CHAND-2024-11849.jpg
# IND      5378  photos/2024_lok_sabha/CHAND-2024-12793.jpg
```

Every candidate in eci_results gets a photo; NOTA rows get none. The join file
also lists Mukeshkumar Dalal, elected unopposed in Surat. eci_results leaves
that seat out, so his key columns are empty.

## How the photos were collected

ECI takes an election's results pages down some months after counting, so each
constituency's candidate page comes from its latest snapshot in the Internet
Archive's Wayback Machine. The pages are committed under
[`data/raw/pages/`](data/raw/pages/) with their snapshot times and SHA-256. A
page gives each candidate's name, party, votes and the URL of the photo. The
photos themselves are still on ECI's server, and all 8,360 came from there.
Requests go out one per second.

Page candidates are matched to eci_results within the seat in two passes. The
first matches on votes and joins 8,248 candidates. The second joins the other
111 by name, letters only. Of those, 46 tied with another candidate in their
seat; the other 65 sit in seats where the archived page caught a count up to
460 votes different from ECI's final report. `join_basis` records the pass. The
build stops if any candidate on either side is left unmatched.

In 8 matched pairs the page's name and eci_results' name share no word, and all
8 are spellings of one name ("BAAL SHOURI CHODABATHINA" and "BALASHOWRI. CH").
ECI's file names often abbreviate or misspell the candidate's name, so they
play no part in the match. One image appears twice: Tarabai Bhovi ran as an
independent in two Karnataka seats with the same photo.

## Rebuild

```sh
make sync
make pages ELECTION=2024_lok_sabha    # archived pages, about 10 minutes
make photos ELECTION=2024_lok_sabha   # parse, join, then photos; about 2.5 hours
```

`make photos` runs the parse and the join first and fetches nothing unless every
candidate is matched. It can be stopped and rerun; photos already in the
manifest are skipped.

## Other elections

ECI's results website has shown photos since the assembly elections of
November 2023, so the same code can collect every election in eci_results. The
Wayback Machine has all 543 Lok Sabha pages but only 237 of the 678 pages for
the November 2023 assemblies.

## License

The code is under the MIT license. The photographs were published by ECI, and
this repository claims no rights in them.
