"""Schema-layer checks: XSD validity, entity-branching matrix, zero-value suppression.

XML parsing uses stdlib ElementTree; lxml is only needed for real XSD validation
and the check degrades to SKIP without it.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

from .core import FAIL, PASS, SKIP, CheckResult

try:
    from lxml import etree
except ImportError:
    etree = None


def _is_zero(text):
    try:
        return Decimal(text) == 0
    except (InvalidOperation, ValueError):
        return False


def run_schema_checks(spec, input_data, xml_path):
    root = ET.parse(str(xml_path)).getroot()
    return [
        _xsd_check(spec, xml_path),
        _branch_check(spec, input_data, root),
        _suppression_check(spec, root),
    ]


def _xsd_check(spec, xml_path):
    if etree is None:
        return CheckResult("schema.xsd", SKIP, "lxml not installed; XSD validation skipped")
    schema = etree.XMLSchema(etree.parse(str(spec["_dir"] / spec["xsd"])))
    doc = etree.parse(str(xml_path))
    if schema.validate(doc):
        return CheckResult("schema.xsd", PASS, "XSD-valid")
    errs = "; ".join(str(e) for e in schema.error_log)
    return CheckResult("schema.xsd", FAIL, errs[:500])


def _branch_check(spec, input_data, root):
    entity = input_data.get("entity_type") if isinstance(input_data, dict) else None
    if not entity:
        return CheckResult("schema.branches", SKIP,
                           "no entity_type given; branching not checked")
    branch = spec["branches"][entity]
    bad = []
    for group in branch.get("require", []):
        if root.find(group) is None:
            bad.append(f"required group {group} missing")
    for group in branch.get("forbid", []):
        if root.find(group) is not None:
            bad.append(f"forbidden group {group} present")
    if bad:
        return CheckResult("schema.branches", FAIL, "; ".join(bad))
    return CheckResult("schema.branches", PASS, f"entity_type={entity} branching OK")


def _suppression_check(spec, root):
    bad = []
    for group in spec["suppression"]["zero_groups"]:
        el = root.find(group)
        if el is None:
            continue
        texts = [(ch.text or "").strip() for ch in el]
        if not texts or all(t == "" or _is_zero(t) for t in texts):
            bad.append(f"{group} present but all-zero (should be suppressed)")
    for group in spec["suppression"]["empty_groups"]:
        el = root.find(group)
        if el is not None and len(el.findall("Row")) == 0:
            bad.append(f"{group} present with no rows (should be suppressed)")
    if bad:
        return CheckResult("schema.suppression", FAIL, "; ".join(bad))
    return CheckResult("schema.suppression", PASS)
