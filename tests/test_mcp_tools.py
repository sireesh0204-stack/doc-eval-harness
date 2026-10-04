import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from mcp_server.server import (_get_form_spec, _list_forms, _validate_output,
                                   _validate_xml)
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


@unittest.skipUnless(HAS_MCP, "mcp SDK not installed")
class McpTools(unittest.TestCase):
    def test_list_forms(self):
        self.assertIn("wv_nipa2", json.loads(_list_forms())["forms"])

    def test_get_form_spec_has_paths_and_xsd(self):
        spec = json.loads(_get_form_spec("wv_nipa2"))
        self.assertTrue(spec["_paths"])
        self.assertIn("<xs:schema", spec["_xsd"])

    def test_validate_output_catches_bug4(self):
        xml = (ROOT / "fixtures" / "xml" / "bug4.xml").read_text(encoding="utf-8")
        payload = (ROOT / "fixtures" / "inputs" / "bug4.json").read_text(encoding="utf-8")
        data = json.loads(_validate_output("wv_nipa2", xml, payload))
        self.assertEqual(data["verdict"], "fail")
        self.assertIn("rules.precision", data["caught"])

    def test_validate_output_passes_good(self):
        xml = (ROOT / "fixtures" / "xml" / "good_corporate.xml").read_text(encoding="utf-8")
        payload = (ROOT / "fixtures" / "inputs" / "good_corporate.json").read_text(encoding="utf-8")
        data = json.loads(_validate_output("wv_nipa2", xml, payload))
        self.assertEqual(data["verdict"], "pass", data["checks"])

    def test_validate_xml_skips_branching_without_entity_type(self):
        xml = (ROOT / "fixtures" / "xml" / "good_corporate.xml").read_text(encoding="utf-8")
        data = json.loads(_validate_xml("wv_nipa2", xml))
        by_id = {c["id"]: c["status"] for c in data["checks"]}
        self.assertEqual(by_id["schema.xsd"], "pass")
        self.assertEqual(by_id["schema.branches"], "skip")


if __name__ == "__main__":
    unittest.main()
