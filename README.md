# MGuStats

Extraction-phase tooling for Mahatma Gandhi University (MGU) UG CBCSS mark lists.

## What the scraper does

`scraper.py` is intentionally narrow:

- submits `PRN + exam_id` requests to the legacy MGU results endpoint
- keeps concurrency throttled with an `asyncio.Semaphore`
- retries timeouts and `502/503/504` responses with exponential backoff
- trims the response down to the result tables or the `Result Not Available` marker
- writes each response to `raw_data/<PRN>/<EXAM_ID>.html`

It does not calculate grades, parse marks into JSON, or do CGPA logic mid-flight.

## Files

- `scraper.py`: async extraction engine
- `metadata.json`: CBCSS exam IDs grouped by semester
- `test.html`: sample real-world result page used for offline trimming checks
- `tests/test_scraper.py`: lightweight offline tests

## Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

The default target URL is taken from the form action embedded in `test.html`. Override it if the portal changes.

```bash
python3 scraper.py --years 23 --counter-start 1 --counter-end 100
```

Useful flags:

- `--years 17 18 19 20 21 22 23`
- `--counter-start 1`
- `--counter-end 120000`
- `--concurrency 12`
- `--max-retries 4`
- `--timeout 15`
- `--target-url https://...`

Notes:

- valid UG CBCSS years are `17` through `23`
- the stream marker is locked to `0021`
- concurrency is intentionally restricted to `10-15`

## Output

Saved files follow this layout:

```text
raw_data/
  230021084506/
    120.html
    147.html
```

If a saved file contains `Result Not Available`, that PRN/exam combination is invalid.

## Tests

```bash
python3 -m unittest discover -s tests
```
