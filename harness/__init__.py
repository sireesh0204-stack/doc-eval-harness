"""doc-eval-harness: layered evaluation for generated form documents.

Schema layer: XSD validity, entity branching, zero-value suppression.
Instruction layer: golden totals recomputed from the input payload, sheet
arithmetic, decimal policy, semantic types.
Render layer: PDF presence + field mapping + pluggable vision judge.
"""
from pathlib import Path

from .core import CaseResult, CheckResult, FAIL, PASS, SKIP, load_cases, load_spec
from .render_checks import MockVisionJudge, VisionJudge, run_render_checks
from .rule_checks import reference, run_rule_checks
from .schema_checks import run_schema_checks

__version__ = "0.1.0"


def run_case(spec, case):
    ref = reference(spec, case["_input"])
    checks = []
    checks += run_schema_checks(spec, case["_input"], case["_xml_path"])
    checks += run_rule_checks(spec, case["_input"], case["_xml_path"], ref)
    checks += run_render_checks(case, ref)
    verdict = "fail" if any(c.status == FAIL for c in checks) else "pass"
    return CaseResult(case["name"], verdict, list(case.get("expected_failures", [])), checks)


def run_suite(spec_dir, cases_path):
    spec = load_spec(Path(spec_dir))
    cases = load_cases(Path(cases_path))
    rows = []
    for case in cases:
        cr = run_case(spec, case)
        caught = set(cr.caught())
        expected = set(cr.expected_failures)
        if not expected:
            outcome = "as_expected" if not caught else "false_fail"
        elif caught == expected:
            outcome = "as_expected"
        else:
            outcome = "mismatch"
        rows.append({
            "case": cr.name,
            "output_verdict": cr.verdict,
            "expected_failures": sorted(expected),
            "caught": sorted(caught),
            "outcome": outcome,
            "checks": [{"id": c.id, "status": c.status, "detail": c.detail} for c in cr.checks],
        })
    as_expected = sum(r["outcome"] == "as_expected" for r in rows)
    return {
        "form": spec["form"],
        "suite_pass": as_expected == len(rows),
        "summary": {"cases": len(rows), "as_expected": as_expected},
        "ambiguities": spec.get("ambiguities", []),
        "cases": rows,
    }
