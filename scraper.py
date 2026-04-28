from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterator, Sequence

from bs4 import BeautifulSoup, FeatureNotFound

try:
    import aiohttp
    from aiohttp import ClientTimeout
except ImportError:  # pragma: no cover - exercised only when deps are missing locally
    aiohttp = None
    ClientTimeout = None


logging.basicConfig(
    level=logging.INFO,
    format="\033[32m%(asctime)s\033[0m - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)

DEFAULT_TARGET_URL = "https://dsdc.mgu.ac.in/exQpMgmt/index.php/public/ResultView_ctrl/"
DEFAULT_METADATA_FILE = Path("metadata.json")
DEFAULT_RAW_DATA_DIR = Path("raw_data")
DEFAULT_CONCURRENCY_LIMIT = 12
DEFAULT_MAX_RETRIES = 4
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_COUNTER_START = 1
DEFAULT_COUNTER_END = 120000
DEFAULT_STREAM_MARKER = "0021"
DEFAULT_YEARS = ("23",)
VALID_YEARS = tuple(f"{year:02d}" for year in range(17, 24))
RETRYABLE_STATUSES = {502, 503, 504}
RESULT_NOT_AVAILABLE = "result not available"
RESULT_FIELD_MARKERS = (
    "permanent register number:",
    "name of student:",
)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}


@dataclass(frozen=True)
class ScrapeConfig:
    target_url: str
    metadata_file: Path
    raw_data_dir: Path
    years: tuple[str, ...]
    stream_marker: str
    counter_start: int
    counter_end: int
    concurrency_limit: int
    max_retries: int
    timeout_seconds: int


@dataclass(frozen=True)
class ScrapeJob:
    prn: str
    exam_id: str


@dataclass(frozen=True)
class ExtractedPayload:
    document: str
    table_count: int
    is_invalid_prn: bool


class RetryableGatewayError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"retryable upstream status {status_code}")
        self.status_code = status_code


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def build_soup(html_content: str) -> BeautifulSoup:
    for parser in ("lxml", "html.parser"):
        try:
            return BeautifulSoup(html_content, parser)
        except FeatureNotFound:
            continue
    return BeautifulSoup(html_content, "html.parser")


def find_result_container(soup: BeautifulSoup):
    invalid_container = None

    for fieldset in soup.find_all("fieldset"):
        text = normalize_text(fieldset.get_text(" ", strip=True)).casefold()
        if not text:
            continue
        if all(marker in text for marker in RESULT_FIELD_MARKERS):
            return fieldset
        if RESULT_NOT_AVAILABLE in text and invalid_container is None:
            invalid_container = fieldset

    if invalid_container is not None:
        return invalid_container

    for table in soup.find_all("table"):
        text = normalize_text(table.get_text(" ", strip=True)).casefold()
        if not text:
            continue
        if all(marker in text for marker in RESULT_FIELD_MARKERS):
            return table.parent or table
        if RESULT_NOT_AVAILABLE in text:
            return table.parent or table

    return None


def find_invalid_message(node) -> str | None:
    for element in node.find_all(["p", "div", "span", "td", "strong"]):
        text = normalize_text(element.get_text(" ", strip=True))
        if RESULT_NOT_AVAILABLE in text.casefold():
            return text

    node_text = normalize_text(node.get_text(" ", strip=True))
    if RESULT_NOT_AVAILABLE in node_text.casefold():
        return "Result Not Available"

    return None


def extract_top_level_tables(container) -> list[str]:
    if getattr(container, "name", None) == "table":
        return [str(container)]

    tables: list[str] = []
    for table in container.find_all("table"):
        if has_table_ancestor_within_container(table, container):
            continue
        tables.append(str(table))
    return tables


def has_table_ancestor_within_container(table, container) -> bool:
    for parent in table.parents:
        if parent is container:
            return False
        if getattr(parent, "name", None) == "table":
            return True
    return False


def render_trimmed_document(fragments: Sequence[str]) -> str:
    lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        '  <meta charset="utf-8" />',
        "  <title>MGU Result Snapshot</title>",
        "</head>",
        "<body>",
    ]
    lines.extend(fragments)
    lines.extend(["</body>", "</html>"])
    return "\n".join(lines)


def extract_trimmed_payload(html_content: str) -> ExtractedPayload | None:
    soup = build_soup(html_content)
    container = find_result_container(soup)

    if container is None:
        invalid_message = find_invalid_message(soup)
        if invalid_message is None:
            return None
        return ExtractedPayload(
            document=render_trimmed_document([f"<p>{escape(invalid_message)}</p>"]),
            table_count=0,
            is_invalid_prn=True,
        )

    tables = extract_top_level_tables(container)
    invalid_message = find_invalid_message(container)
    fragments = list(tables)

    if not fragments and invalid_message is not None:
        fragments.append(f"<p>{escape(invalid_message)}</p>")

    if not fragments:
        return None

    return ExtractedPayload(
        document=render_trimmed_document(fragments),
        table_count=len(tables),
        is_invalid_prn=invalid_message is not None,
    )


def save_payload(raw_data_dir: Path, prn: str, exam_id: str, payload: ExtractedPayload) -> Path:
    save_dir = raw_data_dir / prn
    save_dir.mkdir(parents=True, exist_ok=True)

    file_path = save_dir / f"{exam_id}.html"
    file_path.write_text(payload.document, encoding="utf-8")
    return file_path


def load_exam_ids(metadata_file: Path) -> list[str]:
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    exam_ids: list[str] = []
    seen: set[str] = set()

    for semester_key in sorted(metadata):
        exams = metadata.get(semester_key, [])
        if not isinstance(exams, list):
            continue
        for exam in exams:
            exam_id = str(exam.get("value", "")).strip()
            if not exam_id or exam_id in seen:
                continue
            seen.add(exam_id)
            exam_ids.append(exam_id)

    return exam_ids


def iter_prns(years: Sequence[str], stream_marker: str, start: int, end: int) -> Iterator[str]:
    for year in years:
        for counter in range(start, end + 1):
            yield f"{year}{stream_marker}{counter:06d}"


def total_job_count(years: Sequence[str], exam_ids: Sequence[str], start: int, end: int) -> int:
    return len(years) * (end - start + 1) * len(exam_ids)


def build_payload(prn: str, exam_id: str) -> dict[str, str]:
    return {
        "prn": prn,
        "exam_id": exam_id,
        "btnresult": "Get Result",
    }


async def fetch_html(
    session,
    semaphore: asyncio.Semaphore,
    target_url: str,
    prn: str,
    exam_id: str,
) -> str:
    async with semaphore:
        async with session.post(target_url, data=build_payload(prn, exam_id)) as response:
            if response.status in RETRYABLE_STATUSES:
                raise RetryableGatewayError(response.status)
            if response.status >= 400:
                response.raise_for_status()
            return await response.text(errors="ignore")


def backoff_seconds(attempt_number: int) -> int:
    return 2 ** (attempt_number - 1)


async def fetch_and_save(
    session,
    semaphore: asyncio.Semaphore,
    config: ScrapeConfig,
    job: ScrapeJob,
) -> bool:
    for attempt in range(1, config.max_retries + 1):
        try:
            html_content = await fetch_html(
                session=session,
                semaphore=semaphore,
                target_url=config.target_url,
                prn=job.prn,
                exam_id=job.exam_id,
            )
            payload = extract_trimmed_payload(html_content)
            if payload is None:
                logging.warning(
                    "Skipped %s exam %s because no result container was found.",
                    job.prn,
                    job.exam_id,
                )
                return False

            file_path = save_payload(config.raw_data_dir, job.prn, job.exam_id, payload)
            if payload.is_invalid_prn:
                logging.info("Saved invalid marker: %s", file_path)
            else:
                logging.info("Saved %s (%s tables)", file_path, payload.table_count)
            return True
        except RetryableGatewayError as exc:
            if attempt == config.max_retries:
                logging.error(
                    "Gateway status %s for %s exam %s after %s attempts.",
                    exc.status_code,
                    job.prn,
                    job.exam_id,
                    config.max_retries,
                )
                return False
            delay = backoff_seconds(attempt)
            logging.warning(
                "Gateway status %s for %s exam %s. Retrying in %ss (%s/%s).",
                exc.status_code,
                job.prn,
                job.exam_id,
                delay,
                attempt,
                config.max_retries,
            )
            await asyncio.sleep(delay)
        except asyncio.TimeoutError:
            if attempt == config.max_retries:
                logging.error(
                    "Timed out fetching %s exam %s after %s attempts.",
                    job.prn,
                    job.exam_id,
                    config.max_retries,
                )
                return False
            delay = backoff_seconds(attempt)
            logging.warning(
                "Timed out fetching %s exam %s. Retrying in %ss (%s/%s).",
                job.prn,
                job.exam_id,
                delay,
                attempt,
                config.max_retries,
            )
            await asyncio.sleep(delay)
        except aiohttp.ClientResponseError as exc:
            logging.error(
                "Unexpected HTTP status %s for %s exam %s: %s",
                exc.status,
                job.prn,
                job.exam_id,
                exc,
            )
            return False
        except aiohttp.ClientError as exc:
            if attempt == config.max_retries:
                logging.error(
                    "HTTP client error for %s exam %s after %s attempts: %s",
                    job.prn,
                    job.exam_id,
                    config.max_retries,
                    exc,
                )
                return False
            delay = backoff_seconds(attempt)
            logging.warning(
                "HTTP client error for %s exam %s. Retrying in %ss (%s/%s): %s",
                job.prn,
                job.exam_id,
                delay,
                attempt,
                config.max_retries,
                exc,
            )
            await asyncio.sleep(delay)
        except OSError as exc:
            logging.error("Could not save %s exam %s: %s", job.prn, job.exam_id, exc)
            return False

    return False


async def produce_jobs(queue: asyncio.Queue, config: ScrapeConfig, exam_ids: Sequence[str]) -> None:
    for prn in iter_prns(config.years, config.stream_marker, config.counter_start, config.counter_end):
        for exam_id in exam_ids:
            await queue.put(ScrapeJob(prn=prn, exam_id=exam_id))

    for _ in range(config.concurrency_limit):
        await queue.put(None)


async def worker(queue: asyncio.Queue, session, semaphore: asyncio.Semaphore, config: ScrapeConfig) -> None:
    while True:
        job = await queue.get()
        try:
            if job is None:
                return
            await fetch_and_save(session=session, semaphore=semaphore, config=config, job=job)
        finally:
            queue.task_done()


def require_network_dependencies() -> None:
    if aiohttp is not None and ClientTimeout is not None:
        return
    raise RuntimeError("Install dependencies first: pip install -r requirements.txt")


def validate_config(args: argparse.Namespace) -> ScrapeConfig:
    years = tuple(args.years)
    invalid_years = [year for year in years if year not in VALID_YEARS]
    if invalid_years:
        raise ValueError(
            f"Invalid admission year(s): {', '.join(invalid_years)}. Valid values are {', '.join(VALID_YEARS)}."
        )
    if args.stream_marker != DEFAULT_STREAM_MARKER:
        raise ValueError("The UG CBCSS stream marker must remain 0021.")
    if not 10 <= args.concurrency <= 15:
        raise ValueError("Concurrency must stay between 10 and 15.")
    if args.counter_start < 1 or args.counter_end < args.counter_start:
        raise ValueError("Counter range must be positive and ordered.")
    if args.max_retries < 1:
        raise ValueError("Max retries must be at least 1.")
    if args.timeout < 1:
        raise ValueError("Timeout must be at least 1 second.")

    return ScrapeConfig(
        target_url=args.target_url,
        metadata_file=Path(args.metadata_file),
        raw_data_dir=Path(args.raw_data_dir),
        years=years,
        stream_marker=args.stream_marker,
        counter_start=args.counter_start,
        counter_end=args.counter_end,
        concurrency_limit=args.concurrency,
        max_retries=args.max_retries,
        timeout_seconds=args.timeout,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape trimmed MGU CBCSS result tables into raw_data/<PRN>/<EXAM_ID>.html."
    )
    parser.add_argument("--target-url", default=DEFAULT_TARGET_URL, help="Result form action URL.")
    parser.add_argument("--metadata-file", default=str(DEFAULT_METADATA_FILE), help="Path to metadata.json.")
    parser.add_argument("--raw-data-dir", default=str(DEFAULT_RAW_DATA_DIR), help="Destination root for HTML files.")
    parser.add_argument(
        "--years",
        nargs="+",
        default=list(DEFAULT_YEARS),
        help="Admission year prefixes to scan. Valid values: 17 18 19 20 21 22 23.",
    )
    parser.add_argument("--stream-marker", default=DEFAULT_STREAM_MARKER, help="UG stream marker. Must stay 0021.")
    parser.add_argument("--counter-start", type=int, default=DEFAULT_COUNTER_START, help="Inclusive 6-digit counter start.")
    parser.add_argument("--counter-end", type=int, default=DEFAULT_COUNTER_END, help="Inclusive 6-digit counter end.")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY_LIMIT,
        help="Semaphore and connection-pool limit. Must stay between 10 and 15.",
    )
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Retries for timeouts and gateway failures.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Request timeout in seconds.")
    return parser


async def run(config: ScrapeConfig) -> None:
    require_network_dependencies()

    exam_ids = load_exam_ids(config.metadata_file)
    if not exam_ids:
        raise RuntimeError(f"No exam IDs found in {config.metadata_file}.")

    config.raw_data_dir.mkdir(parents=True, exist_ok=True)

    queue: asyncio.Queue = asyncio.Queue(maxsize=config.concurrency_limit * 4)
    timeout = ClientTimeout(total=config.timeout_seconds)
    connector = aiohttp.TCPConnector(
        limit=config.concurrency_limit,
        limit_per_host=config.concurrency_limit,
    )
    semaphore = asyncio.Semaphore(config.concurrency_limit)

    total_jobs = total_job_count(
        years=config.years,
        exam_ids=exam_ids,
        start=config.counter_start,
        end=config.counter_end,
    )
    logging.info(
        "Queueing %s requests across years %s with %s exam IDs.",
        total_jobs,
        ", ".join(config.years),
        len(exam_ids),
    )

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        headers=DEFAULT_HEADERS,
    ) as session:
        producer = asyncio.create_task(produce_jobs(queue=queue, config=config, exam_ids=exam_ids))
        workers = [
            asyncio.create_task(worker(queue=queue, session=session, semaphore=semaphore, config=config))
            for _ in range(config.concurrency_limit)
        ]

        await producer
        await queue.join()
        await asyncio.gather(*workers)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        config = validate_config(args)
        asyncio.run(run(config))
        return 0
    except KeyboardInterrupt:
        logging.info("Gracefully shutting down engine...")
        return 130
    except (RuntimeError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
