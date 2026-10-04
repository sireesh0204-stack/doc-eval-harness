# doc-eval-harness

Evaluation harness for machine-generated form documents. Three check layers —
schema, instruction, render — over a real regulatory domain: US state tax forms.

**The finding this repo is built to demonstrate:** seven defects taken from a
production tax engine are **all valid against the government XSD**. Schema
validation alone ships every one of them.

```
$ python -m harness --spec specs/wv_nipa2 --cases fixtures/cases.json
good_corporate                       as_expected  -
bug1_row_totals_clobbered            as_expected  rules.sheet.rows
bug2_carryforward_wrong_column       as_expected  rules.sheet.chain, rules.sheet.rows
bug3_stale_amended_total             as_expected  rules.golden
bug4_int_truncated_fiduciary_share   as_expected  rules.precision
bug5_silent_print_failure            as_expected  render.present
bug6_project_number_holds_amount     as_expected  types.project_number
bug7_credit_block_skipped            as_expected  rules.eligible_presence, rules.golden, schema.branches

WV/SchNIPA2: 8/8 cases as expected - SUITE PASS
spec ambiguity on file: fy_aggregate_cap - surface in every report; never silently assert either value
```

## Contents

| Path | What it is |
|---|---|
| `harness/` | the three check layers + the runner |
| `specs/wv_nipa2/` | a spec pack: rule params, entity-branching matrix, XSD-derived path list, ambiguity register |
| `fixtures/` | 1 clean output + 7 defective outputs, each with its input payload and declared expected-catch set |
| `mcp_server/` | the same checks exposed as MCP tools so an agent can self-validate before submitting |
| `promptfoo/` | the same matrix as promptfoo provider evals, plus a script proving the adapter can fail |
| `tests/` | unit tests for the runner, the MCP tool layer, and the check semantics |

## Why three layers

| Layer | Check ids | Catches |
|---|---|---|
| Schema | `schema.xsd`, `schema.branches`, `schema.suppression` | structurally wrong output |
| Instruction | `rules.golden`, `rules.eligible_presence`, `rules.sheet.rows`, `rules.sheet.chain`, `rules.precision`, `types.project_number` | XSD-valid nonsense |
| Render | `render.present`, `render.fields`, `render.vision` | silent print failures, layout drift |

The layers exist because each one is cheaper than the one above it and blind to
what the one below catches:

- **Schema** is nearly free and almost worthless on its own — see the finding above.
- **Instruction** is where correctness lives. Every total is **recomputed from the
  input payload** by a reference implementation and then diffed. It never compares
  against a recorded output, because a recorded output bakes in whatever bug it
  was recorded with.
- **Render** covers the failures that leave no trace in the data: a print error
  swallowed by a bare `return` means the PDF is simply absent, and no XML check
  will ever notice. Deterministic checks handle presence and field mapping; a
  pluggable vision judge handles layout, which is genuinely perceptual.

The rule for where to draw the line: **if the spec lets you compute the truth, it
is code. If the truth is perceptual, it is a judge.** Money is always code.

## Quickstart

```bash
git clone <this-repo> && cd doc-eval-harness
python -m pip install -e .
python -m pip install reportlab        # optional: regenerate the demo printable
python scripts/make_fixture_pdf.py     # optional: demo PDF for the render layer

python -m harness --spec specs/wv_nipa2 --cases fixtures/cases.json
python -m unittest discover -s tests -t .
```

`lxml` and `pypdf` are the only real dependencies; without them the affected checks
report `SKIP` rather than silently passing.

## The suite is self-verifying

`fixtures/cases.json` declares, per case, the set of check ids expected to fire.
The runner exits non-zero unless **every declared defect is caught** and the clean
fixture produces **zero false failures**. That second half is not decoration: a
harness that flags everything is indistinguishable from one that flags nothing, so
both numbers are first-class.

CI enforces this from both directions — it runs the suite, then *removes a defect*
from a fixture and requires the suite to go red. A harness that cannot fail is not
a harness.

## Regression matrix

| Case | Defect (observed in production Go code) | Caught by |
|---|---|---|
| good_corporate | clean output incl. correctly excluded expired carryover | — |
| bug1_row_totals_clobbered | loop wrote the grand total to every row's `Total` | `rules.sheet.rows` |
| bug2_carryforward_wrong_column | Column3 total written into the Column4 "carried forward" field | `rules.sheet.rows`, `rules.sheet.chain` |
| bug3_stale_amended_total | recalculation skipped when a field was non-nil → stale amended return | `rules.golden` |
| bug4_int_truncated_fiduciary_share | money cast through `int()`, losing a 4-decimal fiduciary share | `rules.precision` |
| bug5_silent_print_failure | print error swallowed with a bare `return`; PDF never attached | `render.present` |
| bug6_project_number_holds_amount | credit *amounts* stored in fields named `ProjectNumber` | `types.project_number` |
| bug7_credit_block_skipped | nil guard silently skipped the whole credit block | `schema.branches`, `rules.eligible_presence`, `rules.golden` |

These are **canary fixtures**: a known defect with a declared expected-catch set, so
a check that quietly stops working fails the suite instead of passing it.

## How an eval run works

```
input payload (what the entity did)  →  candidate output (engine / LLM agent)
                                             │
 reference(spec, input) recomputes ──────────┤  golden totals, sheet arithmetic,
                                             │  window/forfeiture rules, precision
                                             ▼
                        three check layers → per-case verdict + JSON report
```

For an LLM agent, point a model at the input payload plus the instructions digest,
collect its XML, and drop it in as the candidate — the same harness scores it. The
fixture XMLs are deterministic stand-ins for agent output, which is why the suite
runs in about a second and costs nothing.

## Running it through promptfoo

The matrix also runs as promptfoo provider evals. No API key: the provider is the
deterministic harness, not a model.

```bash
npx promptfoo eval -c promptfoo/promptfooconfig.yaml     # from the repo root
python promptfoo/verify_adapter.py                        # proves the asserts bind
```

`verify_adapter.py` runs the eval three times — as-is, with a defect removed from a
fixture, and restored — and requires green, then red, then green. An adapter that
only ever goes green converts a regression into a checkmark, so the red run is the
part that matters.

The expected catch sets in `promptfooconfig.yaml` are declared a **second time**,
independently of `cases.json`, so a test fails when the harness and the declaration
disagree. Two independent declarations that agree is evidence; one echoed back is not.

## MCP server

`mcp_server/` exposes the schema and instruction layers as MCP tools so an agent can
check its own output before submitting:

| Tool | Purpose |
|---|---|
| `list_forms()` | available spec packs |
| `get_form_spec(form)` | rule params, branching matrix, path list, XSD — read before generating |
| `validate_xml(form, xml, entity_type?)` | cheap schema-layer pass |
| `validate_output(form, xml, input_payload)` | full golden-diff against recomputed truth |

```json
{"tax-form-validator": {"command": "python", "args": ["-m", "mcp_server"],
                        "cwd": "<path>/doc-eval-harness"}}
```

Round-trip proof: `python scripts/smoke_mcp.py` spawns the server, lists tools, and
catches bug4 (`rules.precision`) across the wire while the clean output passes.

## Spec packs

`specs/<form>/` is `spec.json` (rule params, entity-branching matrix, suppression
groups, ambiguity register) + `paths.txt` (the XSD-derived path list) + the XSD.
Adding a form means adding a spec pack and its rule-pack formulas — the runner and
the check layers are not supposed to change, and if they have to, the abstraction is
wrong and that is worth knowing.

**The ambiguity register is a feature.** The NIPA-2 instructions contradict
themselves on the fiscal-year aggregate cap ($3.0M vs $2.5M). Real specifications
are ambiguous, and a harness that silently picks a reading is worse than useless on
a regulated document. This one surfaces the ambiguity in every report and keeps the
policy decision on the human side of the line.

## Scope and provenance

- Rules are encoded from an instruction digest for the WV Neighborhood Investment
  Program credit (NIPA-2, Rev. 6/2022), simplified for the demo — for example the
  trust share is a percentage of used credit, and unused corporate/partnership
  credit is forfeited per the lines 5a–8f path.
- `nipa2.xsd` is **reconstructed from the documented path list, not the government
  original.** The IRS MeF schemas are gated behind e-Services registration and
  cannot be redistributed; the demo PDF is synthesized. Not affiliated with the
  West Virginia State Tax Department.
- The defect patterns in the regression matrix come from production work; the
  fixture outputs are synthetic stand-ins for artefacts that cannot be published.

## Roadmap

- A second spec pack built on **real public** material (SEC XBRL taxonomy + real
  EDGAR filings), to show the method generalises beyond one form — and to keep the
  schema layer honest by cross-checking against Arelle, the open-source XBRL
  processor the SEC itself uses.
- A real vision backend behind `harness.render_checks.VisionJudge`. Unconfigured
  must report `SKIP`, never a silent pass.
- Failure slicing by check id / entity type / form, with catch rate and false-fail
  rate as headline numbers.
- A trajectory eval: a small tool-loop agent filling the form through the MCP
  server, graded on tool-call sequence as well as final output.
