"""CLI: python -m harness --spec specs/wv_nipa2 --cases fixtures/cases.json"""
import argparse
import json
import sys
from pathlib import Path

from . import run_suite


def main(argv=None):
    ap = argparse.ArgumentParser(prog="harness", description=__doc__)
    ap.add_argument("--spec", required=True, help="spec pack directory")
    ap.add_argument("--cases", required=True, help="cases.json with fixture registry")
    ap.add_argument("--json", dest="json_out", help="write the full JSON report here")
    args = ap.parse_args(argv)

    report = run_suite(args.spec, args.cases)
    for row in report["cases"]:
        caught = ", ".join(row["caught"]) if row["caught"] else "-"
        print(f"{row['case']:36} {row['outcome']:12} {caught}")
    s = report["summary"]
    status = "SUITE PASS" if report["suite_pass"] else "SUITE FAIL"
    print(f"\n{report['form']}: {s['as_expected']}/{s['cases']} cases as expected - {status}")
    for amb in report["ambiguities"]:
        print(f"spec ambiguity on file: {amb['id']} - {amb.get('harness_policy', '')}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["suite_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
