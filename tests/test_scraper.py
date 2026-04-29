import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup

import scraper


REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent


def read_fixture(name: str) -> str:
    return (TESTS_DIR / name).read_text(encoding="utf-8")


class ScraperExtractionTests(unittest.TestCase):
    def test_valid_result_page_keeps_only_result_tables(self) -> None:
        html = read_fixture("valid_result.html")

        payload = scraper.extract_trimmed_payload(html)

        self.assertIsNotNone(payload)
        assert payload is not None
        document_text = BeautifulSoup(payload.document, "html.parser").get_text(" ", strip=True)
        document_text = scraper.normalize_text(document_text)
        self.assertEqual(payload.table_count, 2)
        self.assertFalse(payload.is_invalid_prn)
        self.assertIn("Permanent Register Number:", document_text)
        self.assertIn("SEMESTER RESULT", document_text)
        self.assertNotIn("Get Result", payload.document)
        self.assertNotIn("formValidation.js", payload.document)

    def test_invalid_result_page_is_saved_as_minimal_html(self) -> None:
        html = read_fixture("invalid_result.html")

        payload = scraper.extract_trimmed_payload(html)

        self.assertIsNotNone(payload)
        assert payload is not None
        document_text = BeautifulSoup(payload.document, "html.parser").get_text(" ", strip=True)
        document_text = scraper.normalize_text(document_text)
        self.assertEqual(payload.table_count, 0)
        self.assertTrue(payload.is_invalid_prn)
        self.assertIn("Result Not Available", document_text)
        self.assertNotIn("Get Result", payload.document)
        self.assertNotIn("Select Examination", payload.document)

    def test_load_exam_ids_preserves_unique_values(self) -> None:
        exam_ids = scraper.load_exam_ids(REPO_ROOT / "metadata.json")

        self.assertGreater(len(exam_ids), 0)
        self.assertEqual(len(exam_ids), len(set(exam_ids)))
        self.assertEqual(exam_ids[0], "13")
        self.assertIn("154", exam_ids)

    def test_iter_prns_uses_fixed_ug_stream_marker(self) -> None:
        prns = list(scraper.iter_prns(["22"], "0021", 1, 3))

        self.assertEqual(
            prns,
            [
                "220021000001",
                "220021000002",
                "220021000003",
            ],
        )

    def test_invalid_prns_are_recorded_once_in_raw_data(self) -> None:
        with TemporaryDirectory() as tmpdir:
            raw_data_dir = Path(tmpdir)
            registry = scraper.load_invalid_prn_registry(raw_data_dir)

            first_write = asyncio.run(scraper.record_invalid_prn(registry, "230021000001"))
            second_write = asyncio.run(scraper.record_invalid_prn(registry, "230021000001"))

            self.assertTrue(first_write)
            self.assertFalse(second_write)
            self.assertFalse((raw_data_dir / "230021000001").exists())
            self.assertEqual(
                (raw_data_dir / scraper.INVALID_PRN_LOG_FILENAME).read_text(encoding="utf-8").splitlines(),
                ["230021000001"],
            )

    def test_prn_is_invalid_only_when_every_exam_is_invalid(self) -> None:
        self.assertTrue(
            scraper.should_record_invalid_prn(
                total_exam_count=3,
                invalid_exam_count=3,
                valid_exam_count=0,
                failed_exam_count=0,
            )
        )
        self.assertFalse(
            scraper.should_record_invalid_prn(
                total_exam_count=3,
                invalid_exam_count=1,
                valid_exam_count=1,
                failed_exam_count=1,
            )
        )
        self.assertFalse(
            scraper.should_record_invalid_prn(
                total_exam_count=3,
                invalid_exam_count=2,
                valid_exam_count=0,
                failed_exam_count=1,
            )
        )


if __name__ == "__main__":
    unittest.main()
