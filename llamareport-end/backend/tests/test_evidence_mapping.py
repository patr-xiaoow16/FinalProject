import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agents.evidence_mapping import (  # noqa: E402
    build_evidence_mapping,
    extract_source_reference,
    fallback_evidence_mapping,
)


class EvidenceMappingTests(unittest.IsolatedAsyncioTestCase):
    def test_extract_source_reference_reads_page_and_file(self):
        source = {
            "text": "净息差同比下降0.18个百分点，主要受资产端收益率下行影响。",
            "metadata": {
                "source_file": "平安银行2024年年报.PDF",
                "page_number": 24,
            },
        }

        ref = extract_source_reference(source)

        self.assertEqual(ref["source_page"], "24")
        self.assertEqual(ref["source_file"], "平安银行2024年年报.PDF")
        self.assertIn("净息差同比下降0.18个百分点", ref["evidence"])

    def test_fallback_evidence_mapping_pairs_claims_with_sources(self):
        answer = "盈利能力承压。资本充足性保持稳定。"
        sources = [
            {
                "text": "2024年净息差同比下降0.18个百分点，反映盈利能力承压。",
                "metadata": {"source_file": "平安银行2024年年报.PDF", "page_number": 24},
            },
            {
                "text": "资本充足率13.2%，较上年基本持平。",
                "metadata": {"source_file": "平安银行2024年年报.PDF", "page_number": 56},
            },
        ]

        mapping = fallback_evidence_mapping(answer, sources, max_items=3)

        self.assertEqual(len(mapping), 2)
        self.assertEqual(mapping[0]["claim"], "盈利能力承压")
        self.assertEqual(mapping[0]["source_page"], "24")
        self.assertEqual(mapping[1]["claim"], "资本充足性保持稳定")
        self.assertEqual(mapping[1]["source_page"], "56")

    async def test_build_evidence_mapping_uses_llm_json(self):
        answer = "盈利能力承压，但资本充足性保持稳定。"
        sources = [
            {
                "text": "2024年净息差同比下降0.18个百分点。",
                "metadata": {"source_file": "平安银行2024年年报.PDF", "page_number": 24},
            },
            {
                "text": "资本充足率13.2%，较上年基本持平。",
                "metadata": {"source_file": "平安银行2024年年报.PDF", "page_number": 56},
            },
        ]

        class FakeLLM:
            async def achat(self, messages):
                class FakeResponse:
                    content = """
                    [
                      {
                        "claim": "盈利能力承压",
                        "evidence": "2024年净息差同比下降0.18个百分点。",
                        "source_page": "24",
                        "source_file": "平安银行2024年年报.PDF"
                      }
                    ]
                    """

                return FakeResponse()

        mapping = await build_evidence_mapping(answer, sources, llm=FakeLLM(), max_items=3)

        self.assertEqual(
            mapping,
            [
                {
                    "claim": "盈利能力承压",
                    "evidence": "2024年净息差同比下降0.18个百分点。",
                    "source_page": "24",
                    "source_file": "平安银行2024年年报.PDF",
                }
            ],
        )
