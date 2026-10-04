"""Instruction-layer checks: golden totals, carryover-sheet arithmetic, precision, types.

reference() recomputes expected values from the input payload per the NIPA-2
instructions digest; the candidate XML must agree. Params live in spec.json,
formulas are the NIPA-2 rule pack (add other forms as new rule packs).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .core import FAIL, PASS, SKIP, CheckResult

_D = Decimal
_Q2 = _D("0.01")
_Q4 = _D("0.0001")
_PROJECT_NUMBER = re.compile(r"^[A-Za-z0-9-]+$")

# Golden leaves per entity branch: dotted path -> key in the reference dict.
GOLDEN = {
    "corporate": {
        "CorporateNetIncomeTax.CreditLimit": "line4",
        "CorporateNetIncomeTax.NeighborhoodInvestment": "contributions_total",
        "CorporateNetIncomeTax.RemainingNIPACredit": "remaining",
    },
    "partnership": {
        "CorporateNetIncomeTax.CreditLimit": "line4",
        "CorporateNetIncomeTax.NeighborhoodInvestment": "contributions_total",
        "CorporateNetIncomeTax.RemainingNIPACredit": "remaining",
    },
    "fiduciary": {
        "FiduciaryIncomeTax.CreditLimit": "line4",
        "FiduciaryIncomeTax.RemainingNIPACredit": "remaining",
    },
    "individual": {
        "IndividualIncomeTax.CreditLimit": "line4",
        "IndividualIncomeTax.AmountLineFour": "line4",
        "IndividualIncomeTax.EnterSmallerLineBOrC": "used",
    },
}

_SHEET_COL = {"c3": "Column3Carryover", "c4": "Column4CarryForward",
              "c5": "Column5AccountUsedThisYear", "c6": "Column6RemainingUnusedCredit"}
_SHEET_VALUE = {"c3": "CreditCarryover", "c4": "AmountForward",
                "c5": "AmountUsed", "c6": "RemainingUnused"}


def _q2(d):
    return d.quantize(_Q2, rounding=ROUND_HALF_UP)


def _q4(d):
    return d.quantize(_Q4, rounding=ROUND_HALF_UP)


def reference(spec, inp):
    """Recompute expected NIPA-2 values from the input payload."""
    p = spec["params"]
    ty = int(inp["tax_year"])
    entity = inp["entity_type"]
    rate, in_kind = _D(str(p["credit_rate"])), _D(str(p["in_kind_rate"]))
    lo, hi = _D(str(p["min_contribution"])), _D(str(p["max_contribution"]))
    cap = _D(str(p["annual_credit_cap"]))
    window = int(p["carryover_window_years"])

    contributions = _D("0")
    credit_sum = _D("0")
    eligible_any = False
    for pr in inp.get("projects", []):
        amt = _D(str(pr["contribution"]))
        base = amt * in_kind if pr.get("type") == "in_kind_services" else amt
        contributions += _q2(base)
        if lo <= amt <= hi and int(pr.get("transfer_year", ty)) == ty:
            eligible_any = True
            credit_sum += _q2(base * rate)

    rows = []
    for c in inp.get("carryovers", []):
        by = int(c["begin_year"])
        valid = by <= ty <= by + window - 1
        # Carryover rows keep 4dp: fiduciary-path shares carry to 4 decimal places.
        c3 = _q4(_D(str(c["carryover"])))
        c5 = _q4(_D(str(c["used_this_year"]))) if valid else _D("0.00")
        c4 = c3 if valid else _D("0.00")
        rows.append({"number": str(c["project_number"]), "begin_year": by,
                     "c3": c3, "c4": c4, "c5": c5, "c6": c4 - c5})
    applied = sum((r["c5"] for r in rows), _D("0"))

    line4 = min(credit_sum + applied, cap)
    liability = _q2(_D(str(inp.get("liability_before_credits", "0"))))
    used = min(line4, liability)
    # CNIT path (corporate/partnership): unused credit is forfeited, never carried.
    remaining = _D("0") if entity in ("corporate", "partnership") else line4 - used
    share = _q4(used * _D(str(inp.get("trust_share_pct", "0")))) if entity == "fiduciary" else None
    return {
        "entity": entity, "line4": line4, "used": used, "remaining": remaining,
        "contributions_total": contributions, "share": share,
        "rows": rows, "eligible_any": eligible_any,
        "pdf_fields": {"EntityType": entity, "Line4": str(_q2(line4)),
                       "RemainingNIPACredit": str(_q2(remaining))},
    }


def _find(root, dotted):
    return root.find(dotted.replace(".", "/"))


def _dec(text):
    try:
        return _D(text)
    except (InvalidOperation, ValueError):
        return None


def run_rule_checks(spec, inp, xml_path, ref):
    root = ET.parse(str(xml_path)).getroot()
    entity = inp["entity_type"]
    return [
        _golden_check(entity, root, ref),
        _eligible_presence_check(spec, entity, root, ref),
        *_sheet_checks(root, ref),
        _precision_check(spec, entity, root, ref),
        *_type_checks(root, ref),
    ]


def _golden_check(entity, root, ref):
    bad = []
    for dotted, key in GOLDEN[entity].items():
        el = _find(root, dotted)
        got = (el.text or "").strip() if el is not None else ""
        want = ref[key]
        if not got:
            bad.append(f"{dotted}: missing, expected {want}")
            continue
        val = _dec(got)
        if val is None or val != want:
            bad.append(f"{dotted}: got {got}, expected {want}")
    if bad:
        return CheckResult("rules.golden", FAIL, "; ".join(bad))
    return CheckResult("rules.golden", PASS, f"{entity} leaves match recomputed values")


def _eligible_presence_check(spec, entity, root, ref):
    if not ref["eligible_any"]:
        return CheckResult("rules.eligible_presence", SKIP, "no eligible contribution in input")
    group = spec["branches"][entity]["require"][0]
    if root.find(group) is None:
        return CheckResult("rules.eligible_presence", FAIL,
                           f"eligible contribution present but credit block {group} "
                           "omitted (nil-skip pattern)")
    return CheckResult("rules.eligible_presence", PASS)


def _sheet_checks(root, ref):
    sheet = root.find("InvestmentCarryoverSheet")
    rows_xml = [] if sheet is None else sheet.findall("Row")
    grows = ref["rows"]
    if len(rows_xml) != len(grows):
        detail = f"row count: got {len(rows_xml)}, expected {len(grows)}"
        return [CheckResult("rules.sheet.rows", FAIL, detail),
                CheckResult("rules.sheet.chain", FAIL, detail),
                CheckResult("types.project_number", FAIL, detail)]
    rows_bad, chain_bad = [], []
    for i, (row, g) in enumerate(zip(rows_xml, grows)):
        n = i + 1
        for key, col in _SHEET_COL.items():
            want = g[key]
            t_el = row.find(f"{col}/Total")
            v_el = row.find(f"{col}/{_SHEET_VALUE[key]}")
            t_txt = (t_el.text or "").strip() if t_el is not None else ""
            v_txt = (v_el.text or "").strip() if v_el is not None else ""
            t_val, v_val = _dec(t_txt), _dec(v_txt)
            if t_val is None or t_val != want:
                rows_bad.append(f"row{n} {col}/Total: got {t_txt or 'missing'}, expected {want}")
            if v_val is None or v_val != want:
                chain_bad.append(
                    f"row{n} {col}/{_SHEET_VALUE[key]}: got {v_txt or 'missing'}, expected {want}")
        by = row.find("Column2BeginYear")
        got_by = (by.text or "").strip() if by is not None else "missing"
        if got_by != str(g["begin_year"]):
            chain_bad.append(f"row{n} Column2BeginYear: got {got_by}, expected {g['begin_year']}")
    return [CheckResult("rules.sheet.rows", FAIL if rows_bad else PASS, "; ".join(rows_bad)),
            CheckResult("rules.sheet.chain", FAIL if chain_bad else PASS, "; ".join(chain_bad))]


def _precision_check(spec, entity, root, ref):
    bad = []
    if entity == "fiduciary":
        el = root.find("FiduciaryIncomeTax/TrustEstateShare")
        txt = (el.text or "").strip() if el is not None else ""
        val = _dec(txt)
        want = ref["share"]
        if val is None or val != want:
            bad.append(f"TrustEstateShare: got {txt or 'missing'}, expected {want} "
                       "(fiduciary carries to 4 decimal places)")
        else:
            dp = -val.as_tuple().exponent
            if dp > int(spec["params"]["fiduciary_share_decimals"]):
                bad.append(f"TrustEstateShare: {txt} exceeds "
                           f"{spec['params']['fiduciary_share_decimals']} dp")
    else:
        for dotted in GOLDEN[entity]:
            el = _find(root, dotted)
            if el is None:
                continue
            val = _dec((el.text or "").strip())
            if val is not None and -val.as_tuple().exponent > 2:
                bad.append(f"{dotted}: more than 2 decimal places")
    if bad:
        return CheckResult("rules.precision", FAIL, "; ".join(bad))
    return CheckResult("rules.precision", PASS, "decimal-place policy OK")


def _type_checks(root, ref):
    sheet = root.find("InvestmentCarryoverSheet")
    rows_xml = [] if sheet is None else sheet.findall("Row")
    if len(rows_xml) != len(ref["rows"]):
        return [CheckResult("types.project_number", FAIL,
                            f"row count {len(rows_xml)} != {len(ref['rows'])}")]
    bad = []
    for i, (row, g) in enumerate(zip(rows_xml, ref["rows"])):
        el = row.find("Column1ProjectNumber")
        txt = (el.text or "").strip() if el is not None else ""
        if not _PROJECT_NUMBER.match(txt) or txt != g["number"]:
            bad.append(f"row{i+1} Column1ProjectNumber: {txt!r} is not a project number "
                       f"(expected {g['number']!r}; amount-in-number-field trap)")
    if bad:
        return [CheckResult("types.project_number", FAIL, "; ".join(bad))]
    return [CheckResult("types.project_number", PASS)]
