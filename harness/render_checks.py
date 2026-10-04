"""Render-layer checks: PDF presence, AcroForm field mapping, pluggable vision judge."""
from __future__ import annotations

from pathlib import Path

from .core import FAIL, PASS, SKIP, CheckResult


class VisionJudge:
    """Plug-point for a real VLM judge. Implement judge() to inspect the rendered
    page (rasterized) against the instructions digest: field placement, totals on
    the correct lines, layout. Returns a CheckResult with id 'render.vision'."""

    name = "base"

    def judge(self, pdf_path: Path, instructions: str) -> CheckResult:
        raise NotImplementedError


class MockVisionJudge(VisionJudge):
    name = "mock"

    def judge(self, pdf_path, instructions):
        return CheckResult("render.vision", PASS,
                           "mock judge: no VLM configured; wire a real one here")


def run_render_checks(case, ref, judge=None):
    expected = case.get("_expected_pdf")
    if expected is not None and not expected.exists():
        return [CheckResult("render.present", FAIL,
                            f"expected rendered PDF {expected.name} not found "
                            "(silent print-failure pattern)")]
    pdf = case.get("_pdf_path")
    if pdf is None:
        return []
    if not pdf.exists():
        return [CheckResult("render.fields", SKIP,
                            f"{pdf.name} not generated (run scripts/make_fixture_pdf.py)")]
    results = [CheckResult("render.present", PASS, pdf.name)]
    results.extend(_field_check(pdf, ref))
    results.append((judge or MockVisionJudge()).judge(pdf, "NIPA-2 Rev. 6/2022"))
    return results


def _field_check(pdf, ref):
    try:
        from pypdf import PdfReader
    except ImportError:
        return [CheckResult("render.fields", SKIP, "pypdf not installed")]
    try:
        fields = PdfReader(str(pdf)).get_fields() or {}
    except Exception as exc:
        return [CheckResult("render.fields", FAIL, f"unreadable PDF: {exc}")]
    got = {}
    for name, field in fields.items():
        try:
            value = field.get("/V")
            if isinstance(value, bytes):
                value = value.decode("utf-8", "replace")
            got[name] = "" if value is None else str(value)
        except Exception:
            got[name] = "?"
    bad = []
    for name, want in ref["pdf_fields"].items():
        full = f"SchNIPA2.{name}"
        if got.get(full, "") != want:
            bad.append(f"{full}: got {got.get(full, '<absent>')!r}, expected {want!r}")
    if bad:
        return [CheckResult("render.fields", FAIL, "; ".join(bad))]
    return [CheckResult("render.fields", PASS, f"{len(ref['pdf_fields'])} fields match")]
