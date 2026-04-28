# PROJECT CONTEXT: MGU Consolidated Marks Dashboard (Extraction Phase)

## 1. Project Overview
The objective is to build a consolidated academic marks viewer/dashboard for students of Mahatma Gandhi University (MGU), Kerala, specifically targeting Undergraduate CBCSS programs (like BCA). This repository currently focuses on the **Data Extraction Phase**: safely and efficiently scraping student mark lists from the legacy MGU results portal.\
**Core files:**
* `scraper.py`: The scraper we are building to scrap the marklists from the MGu site.
* `metadata.json`: The file that maps the exam ids to each PRN's year field.

## 2. The Core Discovery: The PRN Schema
The MGU PRN (Permanent Register Number) for UG students is a linear, 12-digit university-wide counter. 

**Format: YY0021XXXXXX**
* `YY` (Digits 1-2): Admission Year (e.g., '22' for 2022, '23' for 2023).
* `0021` (Digits 3-6): The absolute, hardcoded stream marker for ALL Undergraduate Choice Based Credit and Semester System (UG CBCSS) students. This separates UG from PG (0011) or other streams.
* `XXXXXX` (Digits 7-12): A 6-digit global enrollment counter. It starts at `000001` each year and increments linearly as colleges upload admission lists. The maximum ceiling per year is typically around 120,000 to 150,000.

**Database Behavior:**
* Colleges are assigned contiguous blocks of numbers based on when they upload their alphabetical batch lists.
* The database contains "holes" (fragmentation) due to dropouts or unfulfilled capacities. The scraper must expect and gracefully `pass` blank or invalid responses without crashing.

## 3. Exam Metadata (`metadata.json`)
The portal requires an internal `exam_id` to fetch results. 
* We have pre-filtered the university's exam dropdown. All B.Voc and non-CBCS exams have been discarded.
* The valid CBCS exams (Regular and Supplementary) are mapped in `metadata.json` across 6 arrays (`semester_1` to `semester_6`).
* Requests must iterate through these specific IDs.

## 4. Extraction Architecture & Constraints
The scraper is a highly optimized, asynchronous Python engine (`aiohttp`, `asyncio`, `BeautifulSoup` with `lxml`).

**Strict Directives for AI Agents modifying the scraper:**
1.  **Do NOT parse the data mid-flight:** The legacy HTML is messy. The scraper's ONLY job is to fetch the payload, isolate the `<table>` elements, and strip away all other layout CSS/JS and unnecessary HTML. I just want a valid HTML file with only the tables intact and necessary html header. Ensure the scraper does not have the logic to calculate CGPAs or extract specific row values.
2.  **Save Raw HTML:** Trimmed HTML tables must be saved to disk.
    * Directory Structure Rule: `./raw_data/<PRN>/<EXAM_ID>.html`
3.  **Concurrency Limits:** MGU servers might be protected by a state data center WAF. The scraper MUST use an `asyncio.Semaphore` (limit 10-15) to throttle concurrent connections.
4.  **Fault Tolerance:** Implement strict `try/except` blocks with exponential backoff for `502 Bad Gateway` and `504 Gateway Timeout` errors. The university database frequently locks up under load.
5.  **Iteration Strategy:** Do not guess combinations. Lock in the prefix (e.g., `230021`. `23` is the year of the students admission `17`-`23` are the only valid years. `0021` is the UG specification, donot change it.) and iterate the 6-digit suffix sequentially from `000001` up to a predetermined ceiling. If a file contains the string `Result Not Available` then it means the PRN is invalid.

## 5. Next Steps (Post-Extraction)
Once the `./raw_data` directory is populated with trimmed HTML files, a separate parsing module will be developed to walk the directory tree, parse the tables offline, and structure the data into a clean JSON/SQLite format for the frontend dashboard.