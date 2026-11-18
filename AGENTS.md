# Working on this data repository

This is a point-in-time data collection. Follow the [data-repository policy](https://github.com/soodoku/data-repos#maintenance-policy).

- The repository is public and holds photographs of identifiable people, many of them private citizens. Do not add face recognition, embeddings or any inference of sex, caste, religion or age from faces without the owner's explicit decision.
- Photos are committed byte for byte as ECI serves them. Never re-encode, crop or resize a committed photo; every file's SHA-256 is in `data/manifest.csv`.
- Fetch politely: one request per second, through `common.get`. Do not use proxies or other means to reach ECI pages that refuse this connection.
- `make join` must match every candidate to `in-rolls/eci_results` before photos are fetched. Fix a failed join by reading the page, not by loosening the key.
- Do not add blanket CI, pre-commit, version matrices or package-release scaffolding.
