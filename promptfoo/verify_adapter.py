"""Prove the promptfoo adapter can go red, not just green.

An adapter that always passes is worse than no adapter: it converts a real
regression into a green checkmark. This script runs the promptfoo eval twice --
once as-is, once with a defective fixture swapped for a clean one so the declared
catch set can no longer be satisfied -- and requires green then red.

    python promptfoo/verify_adapter.py

Needs Node. Skips (exit 0) if npx or promptfoo is unavailable, so it never blocks
a machine without Node.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = "promptfoo/promptfooconfig.yaml"
TARGET = ROOT / "fixtures" / "xml" / "bug4.xml"
CLEAN = ROOT / "fixtures" / "xml" / "good_corporate.xml"


def run_eval() -> int:
    proc = subprocess.run(
        ["npx", "--yes", "promptfoo@latest", "eval", "-c", CONFIG],
        cwd=ROOT,
        capture_output=True,
        text=True,
        shell=(sys.platform == "win32"),
    )
    return proc.returncode


def main() -> int:
    if shutil.which("npx") is None:
        print("SKIP: npx not on PATH; promptfoo adapter not verified here")
        return 0
    if not TARGET.exists() or not CLEAN.exists():
        print(f"FAIL: missing fixtures ({TARGET.name} / {CLEAN.name})")
        return 2

    original = TARGET.read_text(encoding="utf-8")
    try:
        green = run_eval()
        print(f"baseline run exit={green} (want 0)")
        if green != 0:
            print("FAIL: adapter is red on a passing matrix - it cannot be trusted either way")
            return 2

        # Remove bug4's defect: the declared catch set [rules.precision] is now
        # unsatisfiable, so a binding adapter must exit non-zero.
        TARGET.write_text(CLEAN.read_text(encoding="utf-8"), encoding="utf-8")
        red = run_eval()
        print(f"regressed run exit={red} (want non-zero)")
        if red == 0:
            print("FAIL: adapter stayed green with the defect removed - its asserts are not binding")
            return 2
    finally:
        TARGET.write_text(original, encoding="utf-8")

    restored = run_eval()
    print(f"restored run exit={restored} (want 0)")
    if restored != 0:
        print("FAIL: fixture not restored cleanly")
        return 2

    print("PASS: adapter binds - green on the matrix, red on a removed defect, green after restore")
    return 0


if __name__ == "__main__":
    sys.exit(main())
