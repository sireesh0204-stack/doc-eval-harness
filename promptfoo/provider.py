"""promptfoo custom provider: the doc-eval harness as a deterministic, key-free provider.

promptfoo normally grades model output. Here the "model under test" is the tax
engine (or an LLM agent standing in for it) and the harness is the grader, so this
provider runs no API call at all: it runs the existing regression suite and returns
one case's verdict as structured output. Asserts in promptfooconfig.yaml then
compare that verdict against an expected-catch set declared in the config.

Why bother, when `python -m harness` already reports the same thing: the suite has
to be invocable from the tool the team already runs in CI, and being able to say
"the matrix runs as promptfoo provider evals, no key required" is the difference
between a bespoke script and a portable eval.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness import run_suite  # noqa: E402

_DEFAULT_SPEC = "specs/wv_nipa2"
_DEFAULT_CASES = "fixtures/cases.json"

# One suite run per (spec, cases) per process, however many test rows promptfoo
# asks for. The harness is deterministic, so caching cannot mask a regression
# between rows of a single run.
_CACHE: dict = {}


def _report(spec: str, cases: str) -> dict:
    key = (spec, cases)
    if key not in _CACHE:
        _CACHE[key] = run_suite(ROOT / spec, ROOT / cases)
    return _CACHE[key]


def call_api(prompt, options, context):
    cfg = (options or {}).get("config") or {}
    spec = cfg.get("spec", _DEFAULT_SPEC)
    cases = cfg.get("cases", _DEFAULT_CASES)
    case_name = ((context or {}).get("vars") or {}).get("case")

    try:
        report = _report(spec, cases)
    except Exception as exc:  # surface harness failure as a provider error
        return {"error": f"harness run failed: {exc}"}

    rows = {row["case"]: row for row in report["cases"]}
    if case_name not in rows:
        return {"error": f"unknown case {case_name!r}; known: {sorted(rows)}"}

    row = rows[case_name]
    return {
        "output": json.dumps(
            {
                "case": row["case"],
                "outcome": row["outcome"],
                "caught": sorted(row["caught"]),
                "harness_expected": sorted(row["expected_failures"]),
                "suite_pass": report["suite_pass"],
            },
            sort_keys=True,
        ),
        "metadata": {
            "form": report["form"],
            "suite_pass": report["suite_pass"],
            "output_verdict": row["output_verdict"],
            "ambiguities": [a["id"] for a in report.get("ambiguities", [])],
        },
    }
