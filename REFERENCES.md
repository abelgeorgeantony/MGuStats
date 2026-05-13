# References

## Core Reminders

- UG CBCSS PRN format: `YY0021XXXXXX`
- `0021` is the fixed UG stream marker. Do not change it.
- Scraper output goes to `raw_data/<PRN>/<EXAM_ID>.html`
- Fully invalid PRNs are logged in `raw_data/invalid_prns.txt`
- The scraper should only fetch and trim HTML, not parse marks or calculate CGPA
- Keep concurrency in the `10` to `20` range

## Setup And Run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

```bash
python3 scraper.py --years 23 --counter-start 1 --counter-end 100
```

```bash
python3 scraper.py --years 22 23 --counter-start 1 --counter-end 1000 --concurrency 12 --max-retries 4 --timeout 15
```

Run one exact PRN:

```bash
# 230021084506 -> year 23, counter 84506
python3 scraper.py --years 23 --counter-start 84506 --counter-end 84506
```

Useful reminders:

- `counter-start` and `counter-end` are inclusive
- The 6-digit counter is zero-padded automatically
- A PRN is recorded as invalid only if every exam ID checked for it returns `Result Not Available`

## Tests

```bash
python3 -m unittest discover -s tests
```

## `invalid_prns.txt` Maintenance

Sort in place:

```bash
sort -n -o raw_data/invalid_prns.txt raw_data/invalid_prns.txt
```

Sort and remove duplicates in place:

```bash
sort -n -u -o raw_data/invalid_prns.txt raw_data/invalid_prns.txt
```

Make a backup first if needed:

```bash
cp raw_data/invalid_prns.txt raw_data/invalid_prns.txt.bak
```

Count lines:

```bash
wc -l raw_data/invalid_prns.txt
```

Show duplicates only:

```bash
sort -n raw_data/invalid_prns.txt | uniq -d
```

Search for one exact PRN:

```bash
grep -n '^230021000001$' raw_data/invalid_prns.txt
```

Find malformed lines that are not exactly 12 digits:

```bash
grep -nEv '^[0-9]{12}$' raw_data/invalid_prns.txt
```

Preview the start or end:

```bash
sed -n '1,20p' raw_data/invalid_prns.txt
tail -n 20 raw_data/invalid_prns.txt
```

Note: PRNs are fixed-width 12-digit numbers, so normal sort would also work, but `sort -n` makes the intent obvious.

## Raw Data Inspection

Count saved PRN folders:

```bash
find raw_data -mindepth 1 -maxdepth 1 -type d | wc -l
```

Count saved result HTML files:

```bash
find raw_data -type f -name '*.html' | wc -l
```

List saved exam files for one PRN:

```bash
find raw_data/230021084506 -maxdepth 1 -type f | sort
```

Preview one trimmed HTML file:

```bash
sed -n '1,80p' raw_data/230021084506/120.html
```

## Useful Project Files

- `scraper.py`: async scraper
- `metadata.json`: exam ID source of truth
- `raw_data/invalid_prns.txt`: invalid PRN log
- `tests/test_scraper.py`: offline tests
- `README.md`: usage notes

## Small Things Worth Remembering

- Default target URL is already set in `scraper.py`
- The invalid PRN log is append-only during scraping
- Known invalid PRNs are skipped on future runs
- If `rg` is not installed in the shell, use `find` and `grep`
