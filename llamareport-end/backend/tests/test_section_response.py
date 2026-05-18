import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agents.section_response import build_section_success_response  # noqa: E402


class SectionResponseTests(unittest.TestCase):
    def test_section_response_preserves_sources_and_evidence_mapping(self):
        response = build_section_success_response(
            section_name="financial_review",
            content="分析内容",
            structured_response={"summary": "ok"},
            visualization=None,
            tool_calls=[{"tool_name": "generate_financial_review"}],
            sources=[{"text": "来源片段", "metadata": {"page_number": 24}}],
            evidence_mapping=[{"claim": "盈利承压", "source_page": "24"}],
        )

        self.assertEqual(response["section_name"], "financial_review")
        self.assertEqual(response["sources"][0]["metadata"]["page_number"], 24)
        self.assertEqual(response["evidence_mapping"][0]["source_page"], "24")

    def test_section_response_extracts_inline_source_citation(self):
        response = build_section_success_response(
            section_name="business_guidance",
            content="分析正文\n\n数据来源：平安银行2024年年报第24-25页",
        )

        self.assertEqual(response["source_citation"], "来源：平安银行2024年年报第24-25页")
