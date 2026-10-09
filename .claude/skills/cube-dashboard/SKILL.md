---
name: cube-dashboard
description:
  "Use when checking that Cube matches a Tableau dashboard for the measure rows
  in the Asana project 'Data Marts + Semantic Layer': validating cube-covered
  rows against the live dashboard at every grain, authoring or updating a
  dashboard's checks file, reading a validation report, or posting results to
  Asana. Triggers: 'validate <dashboard> in Cube', 'does Cube match Tableau', a
  mismatch tag, ~/asana-sync/validation, checks/<dashboard>.yml."
---

# cube-dashboard

Validate mode compares Cube with what a Tableau dashboard shows, at every grain
the dashboard's sheets use, for the dashboard's done measure rows in Asana
("Data Marts + Semantic Layer", gid `1213735218595734`). Design:
`docs/superpowers/specs/2026-10-08-cube-validate-skill-design.md`.

A row passes only if every cell at every grain is within tolerance: counts
exactly, rates within 0.1 point. A total can match while a school is far off;
that is the case this exists to catch (#5692).

Verdicts, strongest first: `fail` (a gap nothing explains), `incomplete` (a
grain errored, or a Tableau construct on the row's sheets is unaccounted),
`fix_cube` (every gap is explained, at least one by a mismatch Cube must fix),
`undecided` (every gap is explained, at least one by a mismatch whose fix the
domain owner is deciding), `missing_member` (every gap is explained by a member
Cube lacks), `pass`. Each comment lists the missing members and the explained
mismatches, with who fixes each and the cells they explain.

## Who fixes a mismatch

An explained mismatch is a second formula that reproduces Cube's numbers over
the extract. Every one gets a GitHub issue; its `fix:` says who the issue is
for. The user sets `fix:` when approving the entry, before the run.

| `fix:`      | Means                                                | Issue goes to            | Row                            |
| ----------- | ---------------------------------------------------- | ------------------------ | ------------------------------ |
| `cube`      | The dashboard is right; Cube's formula is not        | The cube builder         | `fix_cube`, tagged `mismatch`  |
| `dashboard` | Cube is right; the dashboard, model or source is not | The dashboard maintainer | Its cells count as matches     |
| `undecided` | The user cannot tell which is intended               | The domain owner         | `undecided`, tagged `mismatch` |

Pick by what is intended:

- The dashboard is the agreed definition and Cube drifted from it (Cube counts
  rows where the dashboard counts students): `cube`.
- The dashboard's formula is plainly broken (DDI's % Completion reads 100%
  everywhere): `dashboard`. Add `where: rpt` or `where: source` when the fix is
  in the model or the source, not the workbook.
- You cannot tell: `undecided`. The owner answers with the label `fix-cube` or
  `fix-dashboard` (or a comment starting with the word), and their issue becomes
  the fix ticket.

Nothing else waits on an undecided mismatch: every row has its own verdict.

## Validate a dashboard

1. Rows. Read the dashboard task's subtasks from Asana; keep the completed ones
   whose notes have `Status:`. Never touch Anthony's six checklist subtasks.
2. Checks. Open `checks/<dashboard>.yml`. For any done row with no entry, author
   one (below). Show new or changed entries to the user and wait for approval
   before running.
3. Follow-up reads. For every `mismatches:` entry with `issue:`, read the issue
   with `mcp__github__issue_read` (`get`, `get_labels`, `get_comments`). A
   closed issue gets `closed_on: <date closed>`, so a fixed one shows as stale.
   On an `undecided` entry, a `fix-cube` or `fix-dashboard` label, or a comment
   whose first word is one of them, sets `fix:` to match; relabel the issue for
   its new side (`cube`, or `tableau`/`dbt`) with `mcp__github__issue_write` (it
   replaces the label set, so pass the whole list) and tell the user to reassign
   it to the cube builder or the dashboard maintainer. A comment on any issue
   saying the other side is wrong goes to the user, who may flip `fix:`. Commit
   the checks file.
4. Run. Write `tests/test_zz_cube_dashboard_run.py` (template below), run
   `uv run pytest tests/test_zz_cube_dashboard_run.py -s -q --tb=short`, then
   delete it. The run downloads the workbook with its extracts and compares Cube
   with the dashboard's own extract, not the live warehouse view. First run with
   `--scope-only`. A `ScopeError` means the Cube identity sees less than the
   dashboard; a `TimingError` means the extract and the Cube fact are more than
   an hour apart (one of them did not refresh). Stop and tell the user either
   way.
5. Renders. For each tab in the entries' `renders:`, call
   `mcp__tableau__get-view-image` once per region (`viewFilters` set to that
   region) and at the worst failing cells. Compare the visible numbers to the
   report. A render that disagrees with the check SQL means the SQL is wrong:
   mark the row `incomplete` in your summary and fix the entry before posting
   anything. A render shows aliased labels (a school id shown as its name); map
   a label back to its value from the column's `<aliases>` in the `.twb` before
   comparing.
6. Review. Walk the user through
   `~/asana-sync/validation/<date>-<dashboard>-fixes.md`, the fix digest. "Fix
   in Cube", "Fix in the dashboard" and "Waiting on the domain owner" come
   first: each mismatch with the cells it explains, the dashboard's formula and
   the other one, and its draft or issue number. A stale entry is closed and
   explains nothing, so remove it. Before the user picks anything to file,
   search the repo's issues (open and closed) with `mcp__github__search_issues`
   for each draft and each row under "Investigate": the problem in plain words,
   the metric, the models and the dashboard. List the matches beside each. The
   same problem becomes the entry's `issue:` instead of a new filing; a related
   one goes in the entry's `related:`, and the draft is rewritten with its
   `Related:` line on the next run. "Add to Cube" lists each missing member that
   explains gaps, merged across rows, with what it is, where it lives and the
   suggested edit. "Investigate" lists each row's gaps nothing explains, with
   the breakdown by its `diagnose_by` field and the dashboard and Cube
   definitions side by side: enough to name the cube or model edit. Note any
   pre-aggregations on failed grains (a stale rollup is a different fix from a
   mart gap). "Unaccounted Tableau constructs" lists what the checks file must
   account for before the row can pass; "Not checked" lists what the check
   deliberately skips, with why.
7. Post. After the user agrees, post the digest once on the dashboard's Asana
   task, then each row's three-line `comment` from
   `~/asana-sync/validation/<date>-<dashboard>.json` verbatim, both with
   `mcp__claude_ai_Asana__add_comment`.
8. Issues. File no draft until the related-issue search in step 6 has run for it
   and the user has seen its matches. A draft whose problem an existing issue
   already tracks is not filed: write that number into the entry's `issue:` and
   comment on the existing issue with the new evidence (cells, rows, run date).
   List each draft in `~/asana-sync/validation/<date>-<dashboard>-issues/` with
   its title and cell count; the user picks which to file. For each pick: create
   it with `mcp__github__issue_write` (`title` and `labels` from the draft's
   first two lines, the rest as `body`; keep only labels
   `mcp__github__get_label` finds), check the returned title and labels, create
   a `#NNNN | <title>` subtask under the checks file's `open_issues_task` with
   `mcp__claude_ai_Asana__create_tasks` (`parent` set, unassigned), and write
   `issue: <number>` into the entry. Commit the checks file. The user assigns
   each issue by its `fix:`: the cube builder, the dashboard maintainer, or (for
   `undecided`) the domain owner.
9. Tags. Tell the user to run `~/asana-sync/sync.py` (preview, then `--apply`).
   It reads `latest.json` and gives every row exactly one validation tag: `pass`
   → `matched`; `fail`, `fix_cube`, `undecided` or `missing_member` → `mismatch`
   (a `missing_member` row also becomes `cube-partial`); `incomplete` or never
   run → `unvalidated`. It ticks a row only when it is both `cube-covered` and
   `matched`, and unticks every other done row. The skill never changes tags or
   ticks itself.

Run template:

```python
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / ".claude/skills/cube-dashboard/checks/<dashboard>.yml"
EXTRA: list[str] = []  # e.g. ["--scope-only"] or ["--rows", "<gid>"]


def test_run() -> None:
    # The pytest fixture loads the secrets; the child process inherits them.
    # tableauhyperapi reads the extract and is not a project dependency.
    cmd = ["uv", "run", "--with", "tableauhyperapi", "scripts/cube_validate.py", "run"]
    cmd += [str(CHECKS), "--as", "<network-scoped email>", *EXTRA]
    print("exit", subprocess.run(cmd, cwd=ROOT).returncode)
```

## Follow up on a dashboard

When the user says something moved ("follow up on DDI": an owner answered, a fix
merged, an issue closed), run only what changed instead of the whole dashboard:

1. Do step 3 above for the dashboard's checks file.
2. Rerun only the rows whose mismatches changed: `--rows <gid,...>` in the run
   template. `latest.json` updates those rows alone; every other row keeps its
   earlier result and date.
3. Walk the user through those rows' digest lines, file any new drafts (steps 6
   and 8), and tell the user to run `sync.py`.

A weekly automatic follow-up is #5842.

## Author a check entry

1. Download the workbook to `.claude/scratch/cube-dashboard/<dashboard>.twb`
   with a throwaway pytest (`tableauserverclient`, `include_extract=False`; it
   appends the extension, so pass the stem).
2. Run `uv run scripts/cube_validate.py grains <twb> --dashboard "<view>" ...`
   with every published view name from `mcp__tableau__get-workbook`, then again
   with `--measure "<caption>"`. Keep its `grains` and each sheet's `formula`.
3. Translate the formula to BigQuery-dialect SQL over the extract's columns,
   which carry the same names as the `rpt_tableau__*` model behind the
   datasource; the run translates it to Hyper's dialect. `grains` resolves field
   copies and expands parameter branches, drill levels and subtotals into
   grains. Match what the dashboard counts, not what the Cube measure counts;
   comment on any deliberate difference.
4. Map every grain dimension in `dimensions:`; one with no Cube member gets
   `cube: null`. Its grains are not comparable, and the dimension is listed as a
   missing member. Also list each such grain without that dimension: the sheet's
   numbers roll up to it.
5. Constructs. `grains --measure` lists every construct on the measure's sheets
   under `constructs`, each with a `ref`: its key plus a fingerprint of what it
   does, so editing a filter or group in the workbook changes the ref and the
   run reports it again. Account for each one:
   - A group or bin: paste its `dimension` snippet, set `kind: relabel` (codes
     rolled into buckets) or `kind: rule` (a definition), and set `cube:` to a
     member whose values equal the bin labels, or leave it null. Values in no
     bin keep their own value; when the dashboard shows an Other bar instead,
     add `other: Other` to the group.
   - A filter, set or source filter: reproduce it in `hard_filters`,
     `cube_filters` or `truth_filters`, reading its mode (exclude, nulls,
     context), not just the field name. A `cube_filters` or `truth_filters`
     entry with `datasource:` applies only beside that extract, for a filter one
     extract's model bakes in. Outputs show a member count, never the values,
     which can be student names; read the values from the `.twb` only for fields
     that are not about a person.
   - An LOD: FIXED ignores every filter except context filters; translate it
     with only those inside.
   - Then list the ref under the file's `handled:` with what reproduces it.
     Anything the check cannot reproduce (table calculations, viewer functions,
     a total that sums rows) goes under the row's `not_checked:` with `why`.

   Set the file's `dashboards:` to the published dashboard names and each
   metric's `tableau:` to its caption; without them the run cannot audit the row
   and marks it `incomplete`.

6. When the formula uses a field Cube lacks (a filter on homeroom, say), list it
   under the metric's `missing_members:` and add the same SQL without it as
   `sql_without` (or `num_without`/`den_without`). When a second formula
   reproduces Cube's numbers (a corrected dashboard formula, or Cube's own
   definition copied over the extract), describe the gap under the file's
   `mismatches:`: `title` as a conventional-commit issue title, `what`, `fix`
   (`cube`, `dashboard` or `undecided`; see "Who fixes a mismatch"), and for a
   dashboard fix an optional `where` (`tableau`, the default, `rpt` or
   `source`), plus optional `evidence`, `labels` and `related` (issue numbers).
   Give the metric a `variants:` entry with that SQL and `explains: [<slug>]`. A
   variant may explain a mismatch and a missing member together; a slug is never
   both. Propose `fix:` with the evidence and let the user set it when they
   approve the entry. Set the file's `open_issues_task:` to the domain's Open
   Issues task gid (Assessments: `1219086050133309`).
7. `count` for sums and distinct counts, `rate` with `num`/`den` for shares
   (within 0.1 point), `average` with `num`/`den` for a mean in its own units,
   such as a scale score (within 0.1 unit). Give a metric
   `diagnose_by: {cube, sql}` when one field explains most definition gaps (the
   attendance code for attendance counts), and describe each missing member
   under the file's `members:` (`what`, `lives_in`, `suggested_edit`) so the
   digest can say what to add. When a measure's sheets read another extract of
   the same workbook, give that metric `datasource:` (the extract's caption); a
   measure shown from two extracts is two metrics in one row, one per
   datasource.
8. Settle. When the window includes the current school year, set `settle.date`
   to the SQL for a row's date and run
   `scripts/cube_validate.py settle <checks>` in the run template (swap `run`
   for `settle` and drop `--as`). Run it late in the day, after the fact's later
   rebuilds. Put its recommended `days` in the entry and show its report to the
   user with the other changes. Its `# settle measured` line goes in the commit
   message, not the file: comments carry no one-off measurements
   (`.claude/rules/comments.md`). Rerun it when the dashboard's refresh schedule
   changes.
9. Check the file loads (`load_checks`), then run the new row alone
   (`--rows <gid>`) so its SQL runs once against the extract.

## Rules

- Aggregates only. Never put student names or ids in a comment, the report, or
  chat. Comments already hide cells under 10 students.
- Mark every dimension whose values name a person: `person: true` for a student
  ("a student" in outputs), `person: a teacher` or another label for staff.
  Every output, issue drafts included, shows the label instead of the value.
- Render only tabs that show aggregates. A roster tab (one row per student)
  renders student names into the session; list it under `renders:` never.
- Never mark a construct handled that the check does not reproduce. A wrong
  `handled:` entry hides the gap the audit exists to show.
- The scratchpad can be wiped: workbooks go in
  `.claude/scratch/cube-dashboard/`, results in `~/asana-sync/validation/`,
  checks in this folder.
- Build mode (work a dashboard's blocking table tasks) plugs in later through
  two things only: append the row's entry here, then
  `run <checks> --rows <gid>`; a built row is done when that returns `pass`.
