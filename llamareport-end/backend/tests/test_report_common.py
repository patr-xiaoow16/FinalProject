import sys
import types
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if "llama_index.core.tools" not in sys.modules:
    llama_index_module = types.ModuleType("llama_index")
    llama_index_core_module = types.ModuleType("llama_index.core")
    llama_index_tools_module = types.ModuleType("llama_index.core.tools")

    class DummyQueryEngineTool:
        pass

    llama_index_tools_module.QueryEngineTool = DummyQueryEngineTool
    sys.modules["llama_index"] = llama_index_module
    sys.modules["llama_index.core"] = llama_index_core_module
    sys.modules["llama_index.core.tools"] = llama_index_tools_module

from agents.report_common import _validate_and_clean_data  # noqa: E402


class ReportCommonTests(unittest.TestCase):
    def test_validate_and_clean_data_preserves_extra_fields_after_validation(self):
        class FakeFinancialReview:
            def __init__(self, **data):
                self.summary = data.get("summary")
                self.company_name = data.get("company_name")
                self.year = data.get("year")

            def model_dump(self):
                return {
                    "summary": self.summary,
                    "company_name": self.company_name,
                    "year": self.year,
                }

        payload = {
            "summary": "财务表现稳定",
            "company_name": "平安银行",
            "year": "2024",
            "sources": [
                {
                    "text": "净息差同比下降0.18个百分点",
                    "metadata": {"page_number": 24, "source_file": "平安银行2024年年报.pdf"},
                }
            ],
        }

        cleaned = _validate_and_clean_data(payload, FakeFinancialReview)

        self.assertIn("sources", cleaned)
        self.assertEqual(cleaned["sources"][0]["metadata"]["page_number"], 24)
