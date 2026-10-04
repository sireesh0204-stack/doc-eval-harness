"""MCP server wrapping the doc-eval-harness check layers as agent tools.

Run:   python -m mcp_server            (stdio; add to any MCP client config)
Smoke: python scripts/smoke_mcp.py     (real stdio round-trip)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness import load_spec, run_case  # noqa: E402
from harness.core import FAIL  # noqa: E402
from harness.schema_checks import run_schema_checks  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("tax-form-validator")


def _spec_dir(form: str) -> Path:
    d = ROOT / "specs" / form
    if not (d / "spec.json").exists():
        raise ValueError(f"unknown form {form!r}; call list_forms() first")
    return d


def _with_temp_xml(xml: str, fn):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8")
    try:
        tmp.write(xml)
        tmp.close()
        return fn(Path(tmp.name))
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def _report(checks):
    caught = [c.id for c in checks if c.status == FAIL]
    return json.dumps({
        "verdict": "fail" if caught else "pass",
        "caught": caught,
        "checks": [{"id": c.id, "status": c.status, "detail": c.detail} for c in checks],
    })


def _list_forms() -> str:
    """List available form spec packs (e.g. wv_nipa2)."""
    specs = ROOT / "specs"
    forms = sorted(p.name for p in specs.iterdir() if (p / "spec.json").exists())
    return json.dumps({"forms": forms})


def _get_form_spec(form: str) -> str:
    """Full spec for a form: rule params, entity-branching matrix, XSD-derived path
    list, and the XSD itself. Read this before generating XML for the form."""
    d = _spec_dir(form)
    spec = json.loads((d / "spec.json").read_text(encoding="utf-8"))
    spec["_paths"] = [
        line.split(": ", 1)[1]
        for line in (d / "paths.txt").read_text(encoding="utf-8").splitlines()
        if ": " in line
    ]
    spec["_xsd"] = (d / spec["xsd"]).read_text(encoding="utf-8")
    return json.dumps(spec)


def _validate_xml(form: str, xml: str, entity_type: str | None = None) -> str:
    """Schema-layer validation of generated form XML: XSD validity, entity branching
    (when entity_type is given), zero-value suppression. Cheap first check."""
    spec = load_spec(_spec_dir(form))
    checks = _with_temp_xml(
        xml, lambda p: run_schema_checks(spec, {"entity_type": entity_type}, p))
    return _report(checks)


def _validate_output(form: str, xml: str, input_payload: str) -> str:
    """Full validation of generated form XML against the written instructions:
    recomputes expected values from the input payload (the taxpayer/entity facts)
    and diffs them against the XML at schema + instruction layers. input_payload is
    the JSON the form engine would receive. Returns verdict, caught check ids, and
    per-check details."""
    spec = load_spec(_spec_dir(form))
    inp = json.loads(input_payload)
    checks = _with_temp_xml(
        xml, lambda p: run_case(spec, {"name": "adhoc", "_input": inp, "_xml_path": p,
                                       "_pdf_path": None, "_expected_pdf": None}).checks)
    return _report(checks)


mcp.tool(name="list_forms")(_list_forms)
mcp.tool(name="get_form_spec")(_get_form_spec)
mcp.tool(name="validate_xml")(_validate_xml)
mcp.tool(name="validate_output")(_validate_output)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
