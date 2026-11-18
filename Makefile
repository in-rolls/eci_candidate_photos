.PHONY: sync pages parse join photos all test lint

ELECTION ?= 2024_lok_sabha

sync:
	uv sync --all-groups

# Archived candidate pages from the Wayback Machine (about 10 minutes per election).
pages:
	uv run python -m eci_candidate_photos.pages $(ELECTION)

parse:
	uv run python -m eci_candidate_photos.parse $(ELECTION)

# Stops if any candidate fails to join to eci_results; run before fetching photos.
join: parse
	uv run python -m eci_candidate_photos.join $(ELECTION)

# One request per second; resumable.
photos: join
	uv run python -m eci_candidate_photos.photos $(ELECTION)

all: pages photos

test:
	uv run pytest -q

lint:
	uv run black --check .
	uv run isort --check-only .
	uv run flake8 src tests
