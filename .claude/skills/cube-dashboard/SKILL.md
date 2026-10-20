---
name: cube-dashboard
description: >-
  Checks a Tableau dashboard's numbers against Cube: captures both once in the
  evening, matches their rows, compares every number, explains each gap, and
  files fixes and Asana tags once hand checks agree. Use when validating Cube
  against a dashboard, re-checking one after a Cube or workbook fix, mapping a
  dashboard's sheets to Cube members, adding a cause to a dashboard's rows
  layer, or reading a validation report. Triggers: "validate <dashboard> against
  Cube", "does Cube match Tableau", cube_validate, ZZ-REVIEW copies in TEMP-CB,
  or any file under .claude/skills/cube-dashboard/checks/.
---

# cube-dashboard

Design: `docs/superpowers/specs/2026-10-15-cube-validate-redesign-design.md`.

## How it works

1. Capture once, in the evening window: the extract, each sheet's export per
   cut, and Cube's rows and answers. Every later step reads that frozen
   snapshot, so analysis is free and repeatable.
2. Reconcile rows on student, day and school: match, value differs, dashboard
   only, Cube only, or outside scope or period.
3. Causes, named SQL rules the analyst approves, claim the gap rows. The rest
   read "unexplained".
4. Each exported number is compared with Cube's at the dashboard's decimals:
   pass, coincidental match, row gap or formula gap.
5. Probes reproduce the dashboard's number and test a candidate rule against
   Cube; a decision records who fixes the gap.
6. Hand checks against Tableau, the captured Cube answer and the SIS gate trust.
   Findings stay held until every one agrees.
7. Follow-ups from a trusted report, after the analyst reviews them: an Asana
   task for dashboard fixes, a GitHub issue for Cube fixes and missing measures.
8. Sync Asana last: verdicts merge into `latest.json`, and
   `scripts/asana_sync.py` sets `matched`, `mismatch` or `unvalidated` and ticks
   done rows.

## Running a step that needs credentials

`plan`, `run`, `answers` and `close` need the Tableau PAT and `CUBE_API_SECRET`;
only the pytest secrets fixture provides them. Write this throwaway file, set
`ARGS`, run it, delete it after the session:

```python
# tests/test_zz_cube_validate.py: throwaway, never committed
import importlib.util
import sys
from pathlib import Path

ARGS = ["run", ".claude/skills/cube-dashboard/checks/<dashboard>.yml"]
PKG = Path(__file__).parents[1] / "scripts" / "cube_validate"


def test_step():
    spec = importlib.util.spec_from_file_location(
        "cube_validate", PKG / "__init__.py", submodule_search_locations=[str(PKG)]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)
    from cube_validate import cli

    assert cli.main(ARGS) == 0
```

Run:
`uv run --with tableauhyperapi pytest tests/test_zz_cube_validate.py -s --tb=short`.
`--tb=short` keeps credentials out of a traceback. `analyze` needs no secrets:
`uv run --with tableauhyperapi python -m scripts.cube_validate analyze <checks>`.

## When to run

The window is in the checks file and differs per dashboard. Attendance: 3:30 PM
to 6:00 AM New York time, after the 3:00 PM extract refresh and Cube's ~3:05 PM
rebuild. Re-check both times in Dagster before relying on them. `run` refuses
outside the window or when the extract predates this window's refresh. A run
that fails its preflight (window or cost cap) creates no snapshot.

- No Tableau MCP calls during a run: they sign in with the same token.
- A capture costs money; analysis is free and can be repeated. Preflight prices
  every query with free dry runs, and a run under the checks file's
  `cost_cap_usd` (default $5) goes ahead without asking. Above it, preflight
  stops and names the dollars and GB.

## Snapshots and resuming

A snapshot is `~/.cache/cube-validate/<dashboard>/<YYYY-MM-DDTHHMM>/`. List that
folder to find the newest.

`run <checks> --snapshot <dir>` resumes an interrupted capture. It resumes only
inside the same window, with unchanged base tables and the same period, and
refuses otherwise.

## First validation of a dashboard

1. `plan <checks>`: downloads the workbook, writes `plan.yml` (sheets, extract
   columns, filter cards, parameters, drafted cuts). Fill `dashboards`,
   `datasource`, `sheets` (stubs) and `cuts`; list under `excluded_sheets`, with
   the reason, every sheet with no Cube counterpart, every sheet on another data
   source ("separate run"), and every sheet that blends 2 data sources
   ("blended, not checked"). List every sheet with a name or student-ID column
   too, with a reason starting `names:` that names the column type, never a
   person (`names: student name column`); coverage reads only those as "only on
   sheets with names". `filter_card_defaults` lists each card's starting value
   per dashboard; a list means the card starts on several values. Copy them into
   `defaults` (a value or a list) and skip `(All)`. A list reads as IN on the
   extract and Cube sides, and a cut's own filter on that card replaces it.
   Defaults differ by dashboard, so 1 checks file covers only the dashboards
   whose defaults match; give the others their own file.
2. Evening 1: `run <checks>`. Rows layer and exports are now frozen. Cells are
   mostly "mapping unproven" or "no Cube counterpart" until mapping.
3. Map from the exports in `<snapshot>/exports/` (see _Mapping a sheet_).
4. Same evening, still in the window: `answers <checks> --snapshot <dir>`. It
   refuses if any base table changed since capture.
5. Build causes from the first report's raw buckets (below), then `analyze`.
6. Work the hand checks (below). Later runs need them only when trust does not
   carry (_Trust across runs_). Then `close <checks>`; the analyst deletes the
   review copy in Tableau and runs `close` again until it reports none left.

Every step after capture (`analyze`, new causes, probes, decisions) runs on the
frozen snapshot. A change that needs new exports or new Cube answers, such as a
new cut or a new mapped column, waits for an evening capture; say so instead of
trying it.

## Mapping a sheet

Declare every column a sheet exports under that sheet: a dim (`dims`), a measure
(`measures`), or the student count (`students`). An undeclared column makes its
rows "no Cube counterpart".

- A dim needs `tableau`, `cube` and `cube_column`; without all three its cells
  read "mapping unproven".
- A measure with no Cube member is declared with `cube: null`.
- Each filter caption goes under `filters`.
- `defaults` holds the values the dashboard's filter cards start on. Every cut
  applies them first, then its own filters, so the default cut stays bare.
  Without them every cut selects rows the dashboard hides, and the student-count
  proof fails.
- A sheet without a student count is proven only by another sheet in the same
  cut that has one and the same filters; otherwise its cells read "mapping
  unproven".
- Cube's `rows.key` part order in the checks file is significant: file order is
  kept.

## Causes

The run starts with none. For each candidate, measure on this snapshot how many
rows it claims and what stays unexplained (`analyze` after adding it), then the
analyst approves it. Causes are SQL over table `rows`: `base`, `k_<key>`,
`t_<extract column>`, `c_<Cube column>`, `t__dup`, `c__dup`. Two causes claiming
one row stop the report; never order them to make it pass.

Set `inert: true` on a cause only when its rows cannot move any mapped measure,
checked against each measure's Cube definition. Its rows then count as matched,
so a cell they sit under can pass. Without it such a cell reads "coincidental
match".

## Measures to cover

The analyst gives a gap-catalog section or an Asana task link. Read it (the
Asana connection, or the repo file) and draft `must_cover:` in the checks file.
The analyst approves it, like causes. The list adds a checklist to the run; the
run still checks everything mapped.

```yaml
must_cover:
  - name: Chronic Absenteeism
    source: https://app.asana.com/0/1/2
    cube:
      {
        member: pct_chronically_absent,
        view: student_attendance_enrollment_periods_view,
      }
    tableau:
      {
        column: Avg. Attendance Metric,
        param: { Attendance Metric: Chronic Absenteeism },
      }
  - name: Late Arrivals
    source: gap catalog, Attendance
    cube: null
    tableau: { column: Late Count }
    rows: [late_flag]
```

- Every value in the example is a placeholder: take the member and view from the
  catalog (the view shown is one the attendance dashboard uses).
- Required: `name`, `source`, `tableau.column`. `param` is a selector caption
  and value, when a selector picks the measure: a value listed under `params`
  for a mapped measure with that column, or the config fails. Omit `param` for
  the selector's default value (the sheet's own `cube`).
- `cube` comes from the catalog's "where" column; `null` when no Cube measure
  exists. The config refuses a `null` entry with no `rows:` (the `rows.compare`
  columns behind the measure).
- An entry's Cube member and view must equal the sheet mapping's for that column
  and value, or the config fails; so does a member where the mapping is `null`.
- A selector value with no Cube measure may carry `measure: null` under
  `params`, so its cut is captured and reads "no Cube counterpart".

## Diagnosing a formula gap

A probe tests a rule that might explain a formula gap. It never sets a verdict.

```yaml
probes:
  - id: chronic-last-day
    measure: Avg. Attendance Metric
    param: { Attendance Metric: Chronic Absenteeism }
    dashboard: select avg(pct) from (select ... from {extract} where {where})
    candidate: select avg(pct) from (select ... from {extract} where {where})
```

- The SQL above is a placeholder; write the measure's own.
- `id` (unique), `measure`, `dashboard` and `candidate` are required. `param` is
  optional.
- Each of `dashboard` and `candidate` is a full query over the raw extract that
  returns 1 value. `{extract}` is the extract table; `{where}` is filled with
  the cut's and the mark's predicates. The tool runs it for every cut, sheet and
  mark the measure appears in, except Cube-only marks (no export to reproduce).
- Return the value in the export's units: a fraction when the format is a
  percent (0.942 for 94.2%).
- Proof: `dashboard` reproduces the export in every judged cell at display
  precision. Without the proof the report shows nothing else.

Steps:

1. Write the probe, then `analyze`.
2. Bring the analyst `### Probes`: the proof, how many cells `candidate` matches
   Cube in, and the table of the rest.
3. Record the analyst's decision (below).

## Decisions

A decision records who fixes a formula gap. The analyst approves it with this
snapshot's numbers.

```yaml
decisions:
  - measure: Avg. Attendance Metric
    param: { Attendance Metric: Chronic Absenteeism }
    owner: dashboard
    rule: The dashboard averages every day, not each student's last day.
    probe: chronic-last-day
    task: ""
```

- `owner`, `measure` and `rule` are required. `owner` is `dashboard`, `cube`, or
  `accepted` (a difference both sides keep on purpose). `measure` must be a
  mapped sheet measure and `param` a value listed under `params` for it. `task`
  is the follow-up link, empty until filed.
- `dashboard` and `cube` need a `probe`. They relabel only the cells where the
  probe's `candidate` matches Cube, as `fix-dashboard` or `fix-cube`. Other
  cells stay "formula gap", so a new gap is never hidden.
- `accepted` needs `cuts` or `sheets` and relabels formula gaps there as
  `accepted difference`.
- Row gaps are not decided here; causes cover them.
- A passing cell counts as resolved where the decision's probe is proven and its
  `candidate` matches Cube (`accepted`: any pass in its cuts or sheets). Remove
  a decision only when a later run shows 0 relabeled and 0 still formula gap.

## Follow-ups

Only from a trusted report.

1. Draft 2 follow-ups: 1 Asana task covering every `dashboard` decision, and 1
   GitHub issue (from `.github/ISSUE_TEMPLATE/feature_request.md`) covering
   every `cube` decision, cube-owned row cause and "in the data, not in Cube"
   line. Aggregates only; counts under 10 as `<10`.
2. Show the drafts. Post nothing until the analyst approves them.
3. File both under the domain's `Open Issues — <Domain>` parent task, in the
   dashboard's section of the Data Marts + Semantic Layer project. Create the
   Asana task with that parent, and link the measure subtasks in its notes.
4. After posting the issue, wait for its TEAMster mirror task,
   `#<N> | <issue title>`, before you continue. Search for `#<N>` until it
   appears; if it is missing after a few minutes, ask the analyst. Then set that
   task's parent to the same `Open Issues — <Domain>` task.
5. Put the posted links in the decisions' `task`.
6. Sync Asana last, with `scripts/asana_sync.py` (rules:
   `references/asana-rules.md`).
   - Draft a merge of this run's verdicts into
     `~/asana-sync/validation/latest.json` (create it if missing), keyed by
     measure subtask gid, keeping every other row: `pass` when every judged cell
     passes or is `fix-dashboard` with a proven probe whose `candidate` matches
     Cube; `fix_cube` for a `cube` decision or a cube-owned row cause; `fail`
     for gaps still open. Rows this run did not judge keep their verdict. The
     analyst runs the merge: the classifier blocks writing that file.
   - Ask the analyst whether `ASANA_PAT` is loaded in their terminal. If not:
     create a personal token at app.asana.com/0/my-apps, then run
     `read -rs ASANA_PAT && export ASANA_PAT`. Never ask for the token in chat.
   - The analyst runs
     `uv run --with requests python scripts/asana_sync.py --only <dashboard task gid>`
     to preview, then adds `--apply`. It sets the tags and ticks done rows.
   - Read the preview before `--apply`. Every change must be on this run's
     measure rows.
   - When the analyst approves a rule that a `Decide:` blocker task asks for,
     comment the decision with this run's numbers and complete the task.
   - A `matched` row ticks done only once all its blockers close. Name the open
     blockers in the report.

## Trust across runs

Trust carries from `~/.cache/cube-validate/<dashboard>/trusted.json`, written by
the last trusted run. A run is trusted without its own hand checks when its
invariants hold, the code and mapping fingerprints match, and no verdict or
bucket appears that the trusted run lacked. The fingerprints ignore `causes`,
`decisions`, `must_cover` and `probes`.

- A new verdict or bucket needs hand checks for only what is new. A changed
  fingerprint (code or mapping) needs a full set.
- A run never carries from its own snapshot, and carried trust still needs that
  run's own invariants.
- If a recorded snapshot later gets a disagreeing hand check, delete its
  `trusted.json` so later runs stop carrying from it.

## Reading the report

- **Trust verdict** opens the report. Trusted only when every invariant holds,
  including "capture completeness" (which `run` records), and every hand check
  agrees (or trust carries). A disagreeing hand check outranks pending ones.
  Findings stay held until then.
- **Coverage** comes next: `## Coverage` has 1 line per `must_cover` entry, in
  this order of precedence: gaps open, covered, in the data not in Cube, not
  judged, not mapped yet, only on sheets with names, not on these dashboards.
  Rows agreeing is evidence, never coverage: covered needs a cell judged against
  a real Cube member.
- **Decisions:** `### Decisions` gives each decision's counts (relabeled, still
  formula gap, resolved). `### Probes` gives each probe's proof and counts, and
  a table of the cells its candidate does not explain.
- **Row buckets:** match, value differs, dashboard only, Cube only, outside
  scope, outside period; each split by cause or "unexplained". Outside scope
  (schools Cube does not show this identity) and outside period (days the run
  did not capture) take no cause.
- **Cells:** pass, coincidental match, row gap, formula gap; under a decision,
  `fix-dashboard`, `fix-cube` or `accepted difference`. Filter ignored, mapping
  unproven, no Cube counterpart and no captured rows are the tool's limits,
  never Cube findings.
- **Precision:** a cell compares at the decimals its sheet shows on the
  dashboard. The review copy drops each measure's number format so exports carry
  the raw value. "Export shows fewer decimals than the dashboard" means that
  drop did not reach the export; the cell is unproven, not equal.
- **Formulas not tested:** mapped measures with no cut whose rows all match.
  Their formulas are unproven either way.
- **Clock risk** counts the rows that changed since capture.
- Counts under 10 show as `<10`, so the report can go to `#data_team`.

## Hand checks

When trust does not carry, `<snapshot>/analysis/hand_checks.md` lists 10 to 15
checks: one per verdict and bucket, plus random passes (only for what is new
when a trusted run exists and the fingerprints match). Tableau side in the
review copy (same frozen extract), Cube side against the captured value, rows
against PowerSchool or Focus. Cube's side is the captured answer at its recorded
refresh time, never today's Cube. Mark each result exactly `agree` or `disagree`
in `hand_checks.yml` (new checks start `pending`), then `analyze`. Any other
value stops `analyze` with an error naming the check's id. A result for a check
no longer picked stays in `hand_checks.yml`; of those, only a `disagree` still
counts toward trust.

## Last year

Once per year, after its logic last changed:
`run <checks> --period 2025-07-01:2026-06-30`. Its snapshot is tagged with the
year and kept until July.

## Rules

- Snapshots hold student-level rows: they stay in `~/.cache/cube-validate/`.
  `hand_checks.md` names students; keep it local.
- The checks file is committed, so it never holds a person's name.
- Review copies go to TEMP-CB only. The tool deletes nothing on Tableau.
