"""Shared types and loaders for the doc-eval harness."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PASS = "pass"
FAIL = "fail"
SKIP = "skip"


@dataclass
class CheckResult:
    id: str
    status: str
    detail: str = ""


@dataclass
class CaseResult:
    name: str
    verdict: str  # "pass" | "fail" for the candidate output
    expected_failures: list
    checks: list

    def caught(self):
        return [c.id for c in self.checks if c.status == FAIL]


def load_spec(spec_dir: Path) -> dict:
    spec_dir = Path(spec_dir)
    spec = json.loads((spec_dir / "spec.json").read_text(encoding="utf-8"))
    spec["_dir"] = spec_dir
    paths = []
    for line in (spec_dir / "paths.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if ": " in line:
            paths.append(line.split(": ", 1)[1])
    spec["_paths"] = paths
    return spec


def load_cases(cases_path: Path) -> list:
    cases_path = Path(cases_path)
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    base = cases_path.parent
    for case in data["cases"]:
        case["_input"] = json.loads((base / case["input"]).read_text(encoding="utf-8"))
        case["_xml_path"] = base / case["xml"]
        case["_pdf_path"] = base / case["pdf"] if case.get("pdf") else None
        case["_expected_pdf"] = base / case["expected_pdf"] if case.get("expected_pdf") else None
    return data["cases"]
