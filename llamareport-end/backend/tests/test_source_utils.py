import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agents.source_utils import coerce_to_mapping, collect_sources_from_payload, merge_sources  # noqa: E402


class SourceUtilsTests(unittest.TestCase):
    def test_coerce_to_mapping_parses_python_dict_string(self):
        raw = "{'summary': 'ok', 'sources': [{'text': '净息差下降', 'metadata': {'page_number': 24}}]}"

        parsed = coerce_to_mapping(raw)

        self.assertEqual(parsed["summary"], "ok")
        self.assertEqual(parsed["sources"][0]["metadata"]["page_number"], 24)

    def test_collect_sources_from_payload_reads_direct_sources(self):
        payload = {
            "summary": "分析摘要",
            "sources": [
                {
                    "text": "净息差同比下降0.18个百分点",
                    "metadata": {"page_number": 24, "source_file": "平安银行2024年年报.pdf"},
                }
            ],
        }

        sources = collect_sources_from_payload(payload)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["metadata"]["page_number"], 24)

    def test_collect_sources_from_payload_reads_raw_output_sources(self):
        payload = {
            "summary": "分析摘要",
            "raw_output": {
                "sources": [
                    {
                        "text": "资本充足率13.2%",
                        "metadata": {"page_number": 56, "source_file": "平安银行2024年年报.pdf"},
                    }
                ]
            },
        }

        sources = collect_sources_from_payload(payload)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["metadata"]["page_number"], 56)

    def test_collect_sources_from_payload_reads_stringified_raw_output_sources(self):
        payload = {
            "raw_output": "{'sources': [{'text': '资本充足率13.2%', 'metadata': {'page_number': 56, 'source_file': '平安银行2024年年报.pdf'}}]}"
        }

        sources = collect_sources_from_payload(payload)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["metadata"]["page_number"], 56)

    def test_merge_sources_deduplicates_by_text_page_and_file(self):
        source = {
            "text": "净息差同比下降0.18个百分点",
            "metadata": {"page_number": 24, "source_file": "平安银行2024年年报.pdf"},
        }

        merged = merge_sources([source], [source], max_items=12)

        self.assertEqual(len(merged), 1)
