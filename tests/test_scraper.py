import unittest
from pathlib import Path

from bs4 import BeautifulSoup

import scraper


REPO_ROOT = Path(__file__).resolve().parents[1]


class ScraperExtractionTests(unittest.TestCase):
    def test_valid_result_page_keeps_only_result_tables(self) -> None:
        html = (REPO_ROOT / "test.html").read_text(encoding="utf-8")

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
        html = """
        <html>
          <body>
            <fieldset class="frame">
              <legend>Result</legend>
              <p>Result Not Available</p>
            </fieldset>
          </body>
        </html>
        """

        payload = scraper.extract_trimmed_payload(html)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload.table_count, 0)
        self.assertTrue(payload.is_invalid_prn)
        self.assertIn("<p>Result Not Available</p>", payload.document)

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


if __name__ == "__main__":
    unittest.main()
