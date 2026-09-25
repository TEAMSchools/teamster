# NJ SLEDS Grade and Credit Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a submission-ready NJ SLEDS Student Course Roster CSV per
region by filling `AlphaGradeEarned` and `CreditsEarned` from the warehouse,
leaving every other column byte-identical to the native PowerSchool extract.

**Architecture:** A BigQuery view in the `cokafor` dataset joins the loaded
extract to `kipptaf_powerschool.stg_powerschool__storedgrades` (stored `Y1`
grades, primary) and `stg_powerschool__pgfinalgrades` (live grades, fills nulls
only). A validation script asserts the handbook's rules and refuses export on
any failure. An export script writes one CSV per region with every value as a
string.

**Tech Stack:** BigQuery (Standard SQL), Python 3.13 via `uv`,
`google-cloud-bigquery` with Application Default Credentials.

Spec:
[`2026-07-30-nj-sleds-grade-credit-backfill-design.md`](../specs/2026-07-30-nj-sleds-grade-credit-backfill-design.md).
Issue [#4630](https://github.com/TEAMSchools/teamster/issues/4630).

## Global Constraints

Every task's requirements implicitly include this section.

- **Only two fields may be written:** `AlphaGradeEarned` and `CreditsEarned`.
  Every other column passes through unchanged from the extract.
- **No row may be added, removed, filtered, or deduplicated.** Row-count parity
  per region is a hard gate: Newark 33,150, Camden 10,343. Row **order** is
  explicitly not preserved: BigQuery's output order across a `union all` with
  left joins is nondeterministic, and no ordinal column was captured at load, so
  the native extract's order is not recoverable. Harmless for a keyed roster
  upload, which matches rows on student and section identifiers, not position.
- **Every value in the view and the CSV is a `STRING`.** No numeric coercion
  anywhere in the export path. CDS codes must keep leading zeros (`07`, not
  `7`).
- **`CreditsEarned` format:** exactly three decimals (`1.000`, `0.000`). The
  handbook sets minimum length 5, so `1` is invalid. Range `0.000`–`35.000`, and
  never greater than that row's `AvailableCredit`.
- **`AlphaGradeEarned` domain** (18 values, handbook page 35): `A` `A+` `A-` `B`
  `B+` `B-` `C` `C+` `C-` `D` `D+` `D-` `E` `E+` `E-` `F` `F+` `F-`. Anything
  else resolves to blank and is reported. Never emit `P` (illegal here) or `F*`
  (a warehouse-internal marker).
- **Grade source precedence:** stored grade always wins; live grades fill nulls
  only.
- **Stored-grade scope:** `academic_year = 2025` and `storecode = 'Y1'`.
- **Live-grade scope:** `enddate` between `2025-07-01` and `2026-06-30`, taking
  the greatest `enddate` per student-section.
- **Region scoping is structural.** Each region branch reads only its own
  extract base table and filters every shared CTE to its own
  `_dbt_source_project` literal (`kippnewark` / `kippcamden`). Local identifiers
  repeat across regions (33 shared student local IDs), so an unqualified join
  manufactures false matches.
- **Grade bands.** `HS` = `sced_level = 'secondary'` and `AvailableCredit`
  greater than `0`. `MS` = prior-to-secondary whose `GradeSpan` **first** two
  characters — the span's lower bound — are in
  `('06','07','08','09','10','11','12')`. Everything else is `OUT` and receives
  no grade. Test membership explicitly rather than with a range comparison: `KG`
  sorts above `06` as a string, so `>= '06'` would wrongly pull in every
  kindergarten row.
- **Never guess.** A conflict or a missing grade produces a blank plus a report
  row, never an inferred value.
- **Python:** always `uv run`. Never bare `python` / `python3`.
- **Worktree:**
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill`.
  Use `git -C <worktree>` on every git call. Read/Edit/Write must target the
  worktree path.
- **No `.sql` files.** sqlfluff is enabled repo-wide and ignored only under
  `src/teamster/**`; a standalone `.sql` under `docs/` is linted with the dbt
  templater and fails outside a dbt project. SQL lives as a Python module
  constant. Keep SQL lines at or under 88 characters so ruff does not flag them.
- **PII:** the exported CSV carries names, dates of birth, and state IDs. It
  stays local and goes only to the state-access uploader. Never commit it, and
  never put row-level values in a commit message, issue, or PR.

## File Structure

All new files live under `docs/superpowers/nj-sleds-roster/submission/`,
matching the precedent set by `docs/superpowers/nj-sleds-roster/setup/` on the
runbook branch, which keeps every NJ SLEDS operational artifact together rather
than adding a seasonal tool to the general-purpose `scripts/` catalog.

| File                     | Responsibility                                                                                                          |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `submission_query.py`    | The SQL as a module constant, plus the column list and the grade domain. No I/O.                                        |
| `validate_submission.py` | Runs every handbook and parity check against the query. Exits non-zero on any failure.                                  |
| `build_submission.py`    | Creates or replaces the view, runs the validation gate, writes one CSV per region. Refuses to export if the gate fails. |
| `README.md`              | How to run the three-step cycle.                                                                                        |

`validate_submission.py` is both the test harness and the permanent pre-upload
gate. Each task adds its checks to it, so every task has a real red-green cycle.

---

### Task 1: Query skeleton, band classification, and parity

**Files:**

- Create: `docs/superpowers/nj-sleds-roster/submission/submission_query.py`
- Create: `docs/superpowers/nj-sleds-roster/submission/validate_submission.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `submission_query.SUBMISSION_SQL` (a `str` holding a bare `SELECT`,
  no trailing semicolon, wrappable as a subquery);
  `submission_query.SUBMISSION_COLUMNS` (a `list[str]` of the 25 submission
  column names in ordinal order); `submission_query.ALPHA_GRADE_DOMAIN` (a
  `frozenset[str]` of the 18 legal letter grades);
  `validate_submission.run_checks(client) -> list[str]` returning a list of
  failure messages (empty means pass).

At the end of this task the query returns all 25 extract columns unchanged plus
`region` and `grade_band`. No grades are resolved yet.

- [ ] **Step 1: Write the failing checks**

Create `validate_submission.py`:

```python
"""Validation gate for the NJ SLEDS student course submission.

Exits non-zero if any handbook or parity rule fails. Prints aggregate counts
only - never row-level values, which are PII.
"""

import sys

from google.cloud import bigquery

from submission_query import SUBMISSION_SQL

PROJECT = "teamster-332318"

EXPECTED_EXTRACT_ROWS = {"newark": 33150, "camden": 10343}
EXPECTED_BAND_ROWS = {
    ("newark", "HS"): 10695,
    ("newark", "MS"): 10746,
    ("newark", "OUT"): 11709,
    ("camden", "HS"): 3648,
    ("camden", "MS"): 3638,
    ("camden", "OUT"): 3057,
}


def _rows(client, sql):
    return list(client.query(sql).result())


def check_row_parity(client):
    """Every extract row appears exactly once. No fan-out, no loss."""
    failures = []
    sql = f"""
    select region, count(*) as n
    from ({SUBMISSION_SQL})
    group by region
    """
    actual = {r.region: r.n for r in _rows(client, sql)}
    for region, expected in EXPECTED_EXTRACT_ROWS.items():
        got = actual.get(region, 0)
        if got != expected:
            failures.append(
                f"row parity {region}: expected {expected}, got {got}"
            )
    return failures


def check_band_counts(client):
    """Band classification matches the spec exactly."""
    failures = []
    sql = f"""
    select region, grade_band, count(*) as n
    from ({SUBMISSION_SQL})
    group by region, grade_band
    """
    actual = {(r.region, r.grade_band): r.n for r in _rows(client, sql)}
    for key, expected in EXPECTED_BAND_ROWS.items():
        got = actual.get(key, 0)
        if got != expected:
            failures.append(
                f"band count {key[0]}/{key[1]}: expected {expected}, got {got}"
            )
    return failures


CHECKS = [check_row_parity, check_band_counts]


def run_checks(client):
    failures = []
    for check in CHECKS:
        failures.extend(check(client))
    return failures


def main():
    client = bigquery.Client(project=PROJECT)
    failures = run_checks(client)
    if failures:
        print(f"FAILED ({len(failures)} issue(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASSED ({len(CHECKS)} check group(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill/docs/superpowers/nj-sleds-roster/submission
uv run --with google-cloud-bigquery python validate_submission.py
```

Expected: `ModuleNotFoundError: No module named 'submission_query'`.

- [ ] **Step 3: Write the query skeleton**

Create `submission_query.py`:

```python
"""SQL and constants for the NJ SLEDS student course submission view.

SUBMISSION_SQL is a bare SELECT with no trailing semicolon so it can be used
as a subquery by the validator or wrapped in CREATE OR REPLACE VIEW by the
builder.
"""

SUBMISSION_COLUMNS = [
    "LocalIdentificationNumber",
    "StateIdentificationNumber",
    "FirstName",
    "LastName",
    "DateOfBirth",
    "CountyCodeAssigned",
    "DistrictCodeAssigned",
    "SchoolCodeAssigned",
    "SectionEntryDate",
    "SectionExitDate",
    "SubjectArea",
    "CourseIdentifier",
    "CourseLevel",
    "GradeSpan",
    "AvailableCredit",
    "CourseSequence",
    "LocalCourseTitle",
    "LocalCourseCode",
    "LocalSectionCode",
    "CreditsEarned",
    "NumericGradeEarned",
    "AlphaGradeEarned",
    "CompletionStatus",
    "CourseType",
    "DualInstitution",
]

ALPHA_GRADE_DOMAIN = frozenset(
    {
        "A", "A+", "A-",
        "B", "B+", "B-",
        "C", "C+", "C-",
        "D", "D+", "D-",
        "E", "E+", "E-",
        "F", "F+", "F-",
    }
)

SUBMISSION_SQL = """
with
    sced as (
        select
            subject_area,
            course_identifier,
            sced_level,
        from `teamster-332318.cokafor.ref_sced_codes`
    ),

    newark_joined as (
        select
            e.*,

            sc.sced_level,

            'newark' as region,
        from `teamster-332318.cokafor.stg_student_extract_newark` as e
        left join sced as sc
            on e.SubjectArea = sc.subject_area
            and e.CourseIdentifier = sc.course_identifier
    ),

    camden_joined as (
        select
            e.*,

            sc.sced_level,

            'camden' as region,
        from `teamster-332318.cokafor.stg_student_extract_camden` as e
        left join sced as sc
            on e.SubjectArea = sc.subject_area
            and e.CourseIdentifier = sc.course_identifier
    ),

    joined as (
        select * from newark_joined
        union all
        select * from camden_joined
    ),

    normalized as (
        select
            *,

            nullif(GradeSpan, '') as grade_span_raw,
            nullif(AvailableCredit, '') as available_credit_raw,
        from joined
    ),

    typed as (
        select
            *,

            lpad(grade_span_raw, 4, '0') as grade_span_padded,
            safe_cast(available_credit_raw as float64) as available_credit_num,
        from normalized
    ),

    banded as (
        select
            *,

            substr(grade_span_padded, 1, 2) as grade_span_start,
        from typed
    ),

    scoped as (
        select
            *,

            case
                when sced_level = 'secondary' and available_credit_num > 0
                then 'HS'
                when
                    grade_span_start
                    in ('06', '07', '08', '09', '10', '11', '12')
                then 'MS'
                else 'OUT'
            end as grade_band,
        from banded
    )

select
    LocalIdentificationNumber,
    StateIdentificationNumber,
    FirstName,
    LastName,
    DateOfBirth,
    CountyCodeAssigned,
    DistrictCodeAssigned,
    SchoolCodeAssigned,
    SectionEntryDate,
    SectionExitDate,
    SubjectArea,
    CourseIdentifier,
    CourseLevel,
    GradeSpan,
    AvailableCredit,
    CourseSequence,
    LocalCourseTitle,
    LocalCourseCode,
    LocalSectionCode,
    CreditsEarned,
    NumericGradeEarned,
    AlphaGradeEarned,
    CompletionStatus,
    CourseType,
    DualInstitution,
    region,
    grade_band,
from scoped
"""
```

- [ ] **Step 4: Run it to confirm it passes**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill/docs/superpowers/nj-sleds-roster/submission
uv run --with google-cloud-bigquery python validate_submission.py
```

Expected: `PASSED (2 check group(s))`. If Camden `MS` is over by 219 and Camden
`OUT` short by the same, the membership test is reading the span's **upper**
bound (characters 3-4) instead of its lower bound (characters 1-2) — `0508` and
`KG08` must land in `OUT`. If `OUT` is short by 1,675, `KG` is being ranked
above `06` by a range comparison instead of the explicit membership list.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/superpowers/nj-sleds-roster/submission/submission_query.py \
  docs/superpowers/nj-sleds-roster/submission/validate_submission.py </dev/null
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill add \
  docs/superpowers/nj-sleds-roster/submission/submission_query.py \
  docs/superpowers/nj-sleds-roster/submission/validate_submission.py
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill commit \
  -m 'feat(nj-sleds): submission query skeleton with band classification (Refs #4630)'
```

---

### Task 2: Stored-grade resolution

**Files:**

- Modify: `docs/superpowers/nj-sleds-roster/submission/submission_query.py`
- Modify: `docs/superpowers/nj-sleds-roster/submission/validate_submission.py`

**Interfaces:**

- Consumes: `SUBMISSION_SQL`, `run_checks` from Task 1.
- Produces: four new columns on the query — `stored_letter` (`STRING`),
  `stored_earned_credit` (`FLOAT64`), `n_stored_letters` (`INT64`),
  `n_stored_credits` (`INT64`).

- [ ] **Step 1: Write the failing checks**

Add to `validate_submission.py`, above the `CHECKS` list:

```python
EXPECTED_STORED_COVERAGE = {
    ("newark", "HS"): 10675,
    ("newark", "MS"): 10682,
    ("camden", "HS"): 3616,
    ("camden", "MS"): 3633,
}


def check_stored_coverage(client):
    """Stored Y1 grades cover the in-scope bands at the measured rate.

    Counts are a floor, not an equality: a re-pulled extract may match more
    rows. A drop signals a broken join.
    """
    failures = []
    sql = f"""
    select region, grade_band, countif(stored_letter is not null) as matched
    from ({SUBMISSION_SQL})
    group by region, grade_band
    """
    actual = {(r.region, r.grade_band): r.matched for r in _rows(client, sql)}
    for key, floor in EXPECTED_STORED_COVERAGE.items():
        got = actual.get(key, 0)
        if got < floor:
            failures.append(
                f"stored coverage {key[0]}/{key[1]}: expected at least "
                f"{floor}, got {got}"
            )
    return failures


def check_no_stored_conflicts(client):
    """No student-section carries conflicting stored Y1 letters or credits.

    Both dimensions matter: stored_letter and stored_earned_credit are
    independent aggregates, so a conflict in either means the pair may not
    come from the same source row.
    """
    sql = f"""
    select
        countif(n_stored_letters > 1) as letter_conflicts,
        countif(n_stored_credits > 1) as credit_conflicts
    from ({SUBMISSION_SQL})
    """
    r = _rows(client, sql)[0]
    failures = []
    if r.letter_conflicts:
        failures.append(
            f"{r.letter_conflicts} row(s) have conflicting stored Y1 letters"
        )
    if r.credit_conflicts:
        failures.append(
            f"{r.credit_conflicts} row(s) have conflicting stored Y1 credits"
        )
    return failures
```

Then extend the list:

```python
CHECKS = [
    check_row_parity,
    check_band_counts,
    check_stored_coverage,
    check_no_stored_conflicts,
]
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill/docs/superpowers/nj-sleds-roster/submission
uv run --with google-cloud-bigquery python validate_submission.py
```

Expected: FAIL with a BigQuery error naming `stored_letter` as unrecognized.

- [ ] **Step 3: Add the stored-grade CTEs**

In `submission_query.py`, insert after the `sced` CTE:

```sql
    stored_raw as (
        select
            _dbt_source_project,
            `grade`,
            earnedcrhrs,

            cast(studentid as string) as studentid_str,
            cast(sectionid as string) as sectionid_str,
        from `teamster-332318.kipptaf_powerschool.stg_powerschool__storedgrades`
        where
            academic_year = 2025
            and storecode = 'Y1'
            and _dbt_source_project in ('kippnewark', 'kippcamden')
    ),

    stored as (
        select
            _dbt_source_project,
            studentid_str,
            sectionid_str,

            max(`grade`) as stored_letter,
            max(earnedcrhrs) as stored_earned_credit,
            count(distinct `grade`) as n_stored_letters,
            count(distinct earnedcrhrs) as n_stored_credits,
        from stored_raw
        group by _dbt_source_project, studentid_str, sectionid_str
    ),

    students as (
        select
            _dbt_source_project,

            cast(student_number as string) as student_number_str,
            cast(id as string) as studentid_str,
        from `teamster-332318.kipptaf_powerschool.stg_powerschool__students`
        where _dbt_source_project in ('kippnewark', 'kippcamden')
    ),
```

Replace both region `_joined` CTEs with these. Each branch reads only its own
extract base table and pins every shared CTE to its own `_dbt_source_project`
literal — that is what makes region separation structural rather than a
predicate someone has to remember.

```sql
    newark_joined as (
        select
            e.*,

            sc.sced_level,
            sg.stored_letter,
            sg.stored_earned_credit,
            sg.n_stored_letters,
            sg.n_stored_credits,

            'newark' as region,
        from `teamster-332318.cokafor.stg_student_extract_newark` as e
        left join sced as sc
            on e.SubjectArea = sc.subject_area
            and e.CourseIdentifier = sc.course_identifier
        left join students as st
            on e.LocalIdentificationNumber = st.student_number_str
            and st._dbt_source_project = 'kippnewark'
        left join stored as sg
            on st.studentid_str = sg.studentid_str
            and e.LocalSectionCode = sg.sectionid_str
            and sg._dbt_source_project = 'kippnewark'
    ),

    camden_joined as (
        select
            e.*,

            sc.sced_level,
            sg.stored_letter,
            sg.stored_earned_credit,
            sg.n_stored_letters,
            sg.n_stored_credits,

            'camden' as region,
        from `teamster-332318.cokafor.stg_student_extract_camden` as e
        left join sced as sc
            on e.SubjectArea = sc.subject_area
            and e.CourseIdentifier = sc.course_identifier
        left join students as st
            on e.LocalIdentificationNumber = st.student_number_str
            and st._dbt_source_project = 'kippcamden'
        left join stored as sg
            on st.studentid_str = sg.studentid_str
            and e.LocalSectionCode = sg.sectionid_str
            and sg._dbt_source_project = 'kippcamden'
    ),
```

Add `stored_letter`, `stored_earned_credit`, `n_stored_letters`, and
`n_stored_credits` to the final `SELECT` list, after `grade_band`.

- [ ] **Step 4: Run it to confirm it passes**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill/docs/superpowers/nj-sleds-roster/submission
uv run --with google-cloud-bigquery python validate_submission.py
```

Expected: `PASSED (4 check group(s))`. If `check_row_parity` now fails with
counts above 33,150 or 10,343, the join fanned out — confirm the `stored` CTE
groups by all three keys and that every join predicate carries its
`_dbt_source_project` literal.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/superpowers/nj-sleds-roster/submission/submission_query.py \
  docs/superpowers/nj-sleds-roster/submission/validate_submission.py </dev/null
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill add \
  docs/superpowers/nj-sleds-roster/submission/submission_query.py \
  docs/superpowers/nj-sleds-roster/submission/validate_submission.py
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill commit \
  -m 'feat(nj-sleds): resolve stored Y1 grades and earned credit (Refs #4630)'
```

---

### Task 3: Live-grade fallback

**Files:**

- Modify: `docs/superpowers/nj-sleds-roster/submission/submission_query.py`
- Modify: `docs/superpowers/nj-sleds-roster/submission/validate_submission.py`

**Interfaces:**

- Consumes: Task 2's `stored_letter`, `n_stored_letters`.
- Produces: `live_letter` (`STRING`), `n_live_letters` (`INT64`).

`pgfinalgrades` has no `academic_year` column and holds history back to 2004, so
it must be scoped by `enddate`. Its `Y1` term stopped being used in 2018; for SY
2025-26 the terminal terms (`Q4`, `H4`, `S4`, `W4`) all end `2026-06-29`. Taking
the greatest `enddate` per student-section therefore selects the terminal term
whatever structure the section uses, without hardcoding a term code.

Two terms can share that same maximum `enddate`, which is a fan-out risk. The
`live` CTE aggregates per student-section and counts distinct letters so a
conflict is reported rather than silently picked.

- [ ] **Step 1: Write the failing checks**

Add to `validate_submission.py`:

```python
def check_no_live_conflicts(client):
    """A conflicted live grade is never emitted as the resolved value.

    Live reporting terms legitimately disagree on tens of thousands of rows -
    several term types close on the same date. That is not an error, because
    on any row with a stored grade the live value is never consulted. The
    invariant that matters is narrower: when live terms disagree, the guard
    must null the value rather than pick one, so grade_source can never be
    'live' on a conflicted row.
    """
    sql = f"""
    select count(*) as n
    from ({SUBMISSION_SQL})
    where n_live_letters > 1 and grade_source = 'live'
    """
    n = _rows(client, sql)[0].n
    if n:
        return [f"{n} row(s) emitted a conflicted live grade"]
    return []


def check_live_fills_only_gaps(client):
    """Live grades never override a stored grade."""
    sql = f"""
    select count(*) as n
    from ({SUBMISSION_SQL})
    where
        stored_letter is not null
        and live_letter is not null
        and stored_letter != live_letter
        and grade_source = 'live'
    """
    n = _rows(client, sql)[0].n
    if n:
        return [f"{n} row(s) took a live grade over a stored grade"]
    return []
```

Extend the list with `check_no_live_conflicts` and `check_live_fills_only_gaps`.

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill/docs/superpowers/nj-sleds-roster/submission
uv run --with google-cloud-bigquery python validate_submission.py
```

Expected: FAIL with a BigQuery error naming `n_live_letters` as unrecognized.

- [ ] **Step 3: Add the live-grade CTEs and the source marker**

Insert after the `stored` CTE:

```sql
    live_raw as (
        select
            _dbt_source_project,
            `grade`,
            enddate,

            cast(studentid as string) as studentid_str,
            cast(sectionid as string) as sectionid_str,
            max(enddate) over (
                partition by _dbt_source_project, studentid, sectionid
            ) as max_enddate,
        from `teamster-332318.kipptaf_powerschool.stg_powerschool__pgfinalgrades`
        where
            enddate between date '2025-07-01' and date '2026-06-30'
            and `grade` is not null
            and _dbt_source_project in ('kippnewark', 'kippcamden')
    ),

    live as (
        select
            _dbt_source_project,
            studentid_str,
            sectionid_str,

            max(`grade`) as live_letter,
            count(distinct `grade`) as n_live_letters,
        from live_raw
        where enddate = max_enddate
        group by _dbt_source_project, studentid_str, sectionid_str
    ),
```

In the **Newark** branch, add these two columns to the select list immediately
after `sg.n_stored_letters,`:

```sql
            lg.live_letter,
            lg.n_live_letters,
```

and this join immediately after the `stored` join:

```sql
        left join live as lg
            on st.studentid_str = lg.studentid_str
            and e.LocalSectionCode = lg.sectionid_str
            and lg._dbt_source_project = 'kippnewark'
```

In the **Camden** branch, add the same two columns in the same position:

```sql
            lg.live_letter,
            lg.n_live_letters,
```

and this join, pinned to Camden:

```sql
        left join live as lg
            on st.studentid_str = lg.studentid_str
            and e.LocalSectionCode = lg.sectionid_str
            and lg._dbt_source_project = 'kippcamden'
```

Insert a CTE after `scoped` that resolves the candidate and records its origin:

```sql
    conflict_guarded as (
        select
            *,

            if(n_stored_letters > 1, null, stored_letter) as safe_stored,
            if(n_live_letters > 1, null, live_letter) as safe_live,
            if(
                n_stored_letters > 1 or n_stored_credits > 1,
                null,
                stored_earned_credit
            ) as safe_stored_credit,
        from scoped
    ),

    sourced as (
        select
            *,

            coalesce(safe_stored, safe_live) as candidate_letter,
            case
                when safe_stored is not null then 'stored'
                when safe_live is not null then 'live'
                else 'none'
            end as grade_source,
        from conflict_guarded
    )
```

Change the final `SELECT` to read `from sourced`, and add `live_letter`,
`n_live_letters`, `candidate_letter`, and `grade_source` to its column list.

- [ ] **Step 4: Run it to confirm it passes**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill/docs/superpowers/nj-sleds-roster/submission
uv run --with google-cloud-bigquery python validate_submission.py
```

Expected: `PASSED (6 check group(s))`. If `check_row_parity` fails high, the
`live` CTE is not collapsing to one row per student-section — verify the
`where enddate = max_enddate` filter sits in the `live` CTE, not `live_raw`.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/superpowers/nj-sleds-roster/submission/submission_query.py \
  docs/superpowers/nj-sleds-roster/submission/validate_submission.py </dev/null
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill add \
  docs/superpowers/nj-sleds-roster/submission/submission_query.py \
  docs/superpowers/nj-sleds-roster/submission/validate_submission.py
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill commit \
  -m 'feat(nj-sleds): add live-grade fallback with conflict guard (Refs #4630)'
```

---

### Task 4: Field emission and formatting

**Files:**

- Modify: `docs/superpowers/nj-sleds-roster/submission/submission_query.py`
- Modify: `docs/superpowers/nj-sleds-roster/submission/validate_submission.py`

**Interfaces:**

- Consumes: Task 3's `candidate_letter`, `grade_source`; Task 2's
  `stored_earned_credit`; Task 1's `grade_band`, `available_credit_num`.
- Produces: the final `AlphaGradeEarned` and `CreditsEarned` columns, replacing
  the extract's own (which are empty and `0.000` respectively).

- [ ] **Step 1: Write the failing checks**

Add to `validate_submission.py`, importing the domain at the top
(`from submission_query import ALPHA_GRADE_DOMAIN, SUBMISSION_SQL`):

```python
def check_alpha_grade_domain(client):
    """Every emitted letter grade is one of the 18 legal handbook values."""
    domain = ", ".join(f"'{g}'" for g in sorted(ALPHA_GRADE_DOMAIN))
    sql = f"""
    select count(*) as n
    from ({SUBMISSION_SQL})
    where AlphaGradeEarned is not null
      and AlphaGradeEarned not in ({domain})
    """
    n = _rows(client, sql)[0].n
    if n:
        return [f"{n} row(s) carry an out-of-domain AlphaGradeEarned"]
    return []


def check_in_scope_rows_have_grades(client):
    """No in-scope row is left without a letter grade."""
    sql = f"""
    select region, grade_band, count(*) as n
    from ({SUBMISSION_SQL})
    where grade_band in ('HS', 'MS') and AlphaGradeEarned is null
    group by region, grade_band
    """
    return [
        f"{r.n} in-scope row(s) in {r.region}/{r.grade_band} have no grade"
        for r in _rows(client, sql)
    ]


def check_out_of_scope_rows_blank(client):
    """Out-of-scope rows carry no grade and no credit. Scope-boundary guard."""
    sql = f"""
    select count(*) as n
    from ({SUBMISSION_SQL})
    where grade_band = 'OUT'
      and (AlphaGradeEarned is not null or CreditsEarned is not null)
    """
    n = _rows(client, sql)[0].n
    if n:
        return [f"{n} out-of-scope row(s) were given a grade or credit"]
    return []


def check_credits_earned(client):
    """CreditsEarned is present, 3-decimal, in range, and within available."""
    sql = f"""
    select
        countif(grade_band = 'HS' and CreditsEarned is null) as missing,
        countif(
            CreditsEarned is not null
            and not regexp_contains(CreditsEarned, r'^[0-9]+\\.[0-9]{{3}}$')
        ) as malformed,
        countif(
            CreditsEarned is not null
            and safe_cast(CreditsEarned as float64) not between 0.0 and 35.0
        ) as out_of_range,
        countif(
            CreditsEarned is not null
            and safe_cast(CreditsEarned as float64)
                > safe_cast(nullif(AvailableCredit, '') as float64)
        ) as over_available
    from ({SUBMISSION_SQL})
    """
    r = _rows(client, sql)[0]
    failures = []
    if r.missing:
        failures.append(f"{r.missing} HS row(s) missing CreditsEarned")
    if r.malformed:
        failures.append(
            f"{r.malformed} row(s) CreditsEarned not 3-decimal formatted"
        )
    if r.out_of_range:
        failures.append(
            f"{r.out_of_range} row(s) CreditsEarned outside 0.000-35.000"
        )
    if r.over_available:
        failures.append(
            f"{r.over_available} row(s) CreditsEarned exceeds AvailableCredit"
        )
    return failures
```

Extend the list with all four.

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill/docs/superpowers/nj-sleds-roster/submission
uv run --with google-cloud-bigquery python validate_submission.py
```

Expected: FAIL — `check_credits_earned` reports 14,343 HS rows malformed,
because `CreditsEarned` is still the extract's `0.000`... which is in fact
correctly formatted, so the concrete failure is
`check_in_scope_rows_have_grades` reporting 28,727 rows with no grade.

- [ ] **Step 3: Add the emission CTEs**

Insert after `sourced`:

```sql
    emitted_grade as (
        select
            *,

            if(
                grade_band in ('HS', 'MS')
                and candidate_letter in (
                    'A', 'A+', 'A-', 'B', 'B+', 'B-',
                    'C', 'C+', 'C-', 'D', 'D+', 'D-',
                    'E', 'E+', 'E-', 'F', 'F+', 'F-'
                ),
                candidate_letter,
                cast(null as string)
            ) as emitted_alpha_grade,
        from sourced
    ),

    emitted_credit as (
        select
            *,

            case
                when grade_band != 'HS'
                then cast(null as string)
                when safe_stored_credit is not null
                then format('%.3f', safe_stored_credit)
                when emitted_alpha_grade is null
                then cast(null as string)
                when emitted_alpha_grade like 'F%'
                then '0.000'
                else format('%.3f', available_credit_num)
            end as emitted_credits_earned,
        from emitted_grade
    )
```

In the final `SELECT`, replace the two pass-through columns:

```sql
    emitted_credits_earned as CreditsEarned,
```

in position 20, and:

```sql
    emitted_alpha_grade as AlphaGradeEarned,
```

in position 22. Change `from sourced` to `from emitted_credit`. Keep the other
23 submission columns exactly as they are, and keep the audit columns (`region`,
`grade_band`, `grade_source`) at the end.

Note the credit precedence: the stored earned-credit value wins whenever it
exists, because it is PowerSchool's own record of credit awarded. The derived
rule applies only to rows whose grade came from the live fallback and which have
no earned-credit value — measured at exactly 2 rows. (52 is the count of
secondary/HS gap rows overall; most of those have no grade in any source at all
and never reach this rule.) Sourcing the fallback value from the row's own
`AvailableCredit` makes the must-not-exceed constraint unviolatable.

The credit path reads `safe_stored_credit`, not `stored_earned_credit`. That
column is null whenever a student-section has conflicting stored letters **or**
conflicting stored credit values, because `stored_letter` and
`stored_earned_credit` are independent aggregates with no guaranteed row
correspondence — on a conflicted student-section, the pair may come from
different source rows. Guarding both dimensions keeps a conflicted row from
emitting a credit alongside a blank grade.

- [ ] **Step 4: Run it to confirm it passes**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill/docs/superpowers/nj-sleds-roster/submission
uv run --with google-cloud-bigquery python validate_submission.py
```

Expected: `PASSED (10 check group(s))`.

`check_in_scope_rows_have_grades` **will** report a residue, and that is
expected, not a defect. Measured against the strict band rule: 121 in-scope rows
have no stored grade; roughly a dozen of those resolve from the live fallback,
and the rest have no grade in either source — meaning PowerSchool holds none, so
the native extract could not produce one either.

Do not relax or waive the check, and do not invent values for those rows. They
are a PowerSchool worklist: someone must post the missing grades or exclude
those sections before upload. Report the residue as an aggregate count broken
down by region and band, and hand it to the user with the final task report.

This is the one check that is expected to fail on the current data, so
`build_submission.py` in Task 6 will refuse to export until the source data is
fixed. That is the gate working as designed.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/superpowers/nj-sleds-roster/submission/submission_query.py \
  docs/superpowers/nj-sleds-roster/submission/validate_submission.py </dev/null
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill add \
  docs/superpowers/nj-sleds-roster/submission/submission_query.py \
  docs/superpowers/nj-sleds-roster/submission/validate_submission.py
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill commit \
  -m 'feat(nj-sleds): emit AlphaGradeEarned and CreditsEarned (Refs #4630)'
```

---

### Task 5: Prove the gate fires

**Files:**

- Modify: `docs/superpowers/nj-sleds-roster/submission/validate_submission.py`

**Interfaces:**

- Consumes: `run_checks` and all ten check groups.
- Produces: no new columns. Adds
  `validate_submission.self_test(client) -> list[str]`, reached only via the
  `--self-test` flag.

A gate that has never failed is not known to work. This task deliberately
corrupts the query in memory and asserts that each check group catches it.

- [ ] **Step 1: Write the self-test**

Add to `validate_submission.py`:

````python
First give every check function an optional `sql` keyword argument defaulting to
`SUBMISSION_SQL`, and have each one interpolate `sql` rather than
`SUBMISSION_SQL` in its query:

```python
def check_alpha_grade_domain(client, sql=SUBMISSION_SQL):
````

`run_checks` still calls `check(client)`, so the real gate is byte-for-byte
unchanged in behavior. This exists so the self-test can point the **actual**
check at a mutated query.

Then add the self-test, which calls those real functions:

```python
def self_test(client):
    """Prove the real checks fire on injected defects. Mutates SQL in memory.

    Each block calls the ACTUAL check function against the mutated SQL, so
    widening a check's domain or weakening its predicate makes this
    self-test fail. A self-test that re-implements the check's own predicate
    would keep passing with the check's logic gutted, which is worse than no
    self-test at all - it manufactures false confidence.

    This does not prove every check still runs as part of the gate: it calls
    two check functions directly by name, so it covers 2 of the 11 check
    groups in CHECKS.
    """
    failures = []

    # An out-of-domain grade must be caught by check_alpha_grade_domain.
    bad_domain = SUBMISSION_SQL.replace(
        "candidate_letter,\n                cast(null as string)",
        "'F*',\n                cast(null as string)",
    )
    if bad_domain == SUBMISSION_SQL:
        failures.append("self-test could not inject a bad grade domain")
    elif not check_alpha_grade_domain(client, sql=bad_domain):
        failures.append("check_alpha_grade_domain missed an 'F*' grade")

    # A 1-decimal credit must be caught by check_credits_earned.
    bad_format = SUBMISSION_SQL.replace("format('%.3f'", "format('%.1f'")
    if bad_format == SUBMISSION_SQL:
        failures.append("self-test could not inject a bad credit format")
    elif not any(
        "3-decimal" in f for f in check_credits_earned(client, sql=bad_format)
    ):
        failures.append("check_credits_earned missed a 1-decimal credit")

    return failures
```

Note the asymmetry in the two assertions. `check_alpha_grade_domain` returns an
empty list on clean data, so a plain truthiness test suffices.
`check_credits_earned` already returns a `missing = 50` failure on clean data,
so a truthiness test would pass even with the format clause broken — the
self-test must look for the **specific** failure string.

````python

Wire it into `main` behind a flag:

```python
def main():
    client = bigquery.Client(project=PROJECT)
    if "--self-test" in sys.argv:
        failures = self_test(client)
        if failures:
            print(f"SELF-TEST FAILED ({len(failures)}):")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("SELF-TEST PASSED")
        return 0
    failures = run_checks(client)
    ...
````

- [ ] **Step 2: Run the self-test**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill/docs/superpowers/nj-sleds-roster/submission
uv run --with google-cloud-bigquery python validate_submission.py --self-test
```

Expected: `SELF-TEST PASSED`. A "could not inject" failure means the string
targets drifted from the query — update the replacement targets, do not delete
the self-test.

- [ ] **Step 3: Confirm the real gate still passes**

```bash
uv run --with google-cloud-bigquery python validate_submission.py
```

Expected: `PASSED (10 check group(s))`.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/superpowers/nj-sleds-roster/submission/validate_submission.py </dev/null
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill add \
  docs/superpowers/nj-sleds-roster/submission/validate_submission.py
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill commit \
  -m 'test(nj-sleds): prove the validation gate catches injected defects (Refs #4630)'
```

---

### Task 6: View creation, export, and runbook

**Files:**

- Create: `docs/superpowers/nj-sleds-roster/submission/build_submission.py`
- Create: `docs/superpowers/nj-sleds-roster/submission/README.md`

**Interfaces:**

- Consumes: `submission_query.SUBMISSION_SQL`,
  `submission_query.SUBMISSION_COLUMNS`, `validate_submission.run_checks`.
- Produces: the view `cokafor.rpt_student_course_submission`, and one CSV per
  region at a caller-supplied output directory.

- [ ] **Step 1: Write the export script**

Create `build_submission.py`:

```python
"""Create the NJ SLEDS submission view and export one CSV per region.

Refuses to export if the validation gate reports any failure. Every value is
written as the string the view produced - no numeric coercion, so 3-decimal
credits and leading-zero CDS codes survive.

Usage:
    uv run --with google-cloud-bigquery python build_submission.py OUTDIR
"""

import csv
import sys
from pathlib import Path

from google.cloud import bigquery

from submission_query import SUBMISSION_COLUMNS, SUBMISSION_SQL
from validate_submission import run_checks

PROJECT = "teamster-332318"
VIEW = "teamster-332318.cokafor.rpt_student_course_submission"
REGIONS = ("newark", "camden")


def create_view(client):
    client.query(f"create or replace view `{VIEW}` as {SUBMISSION_SQL}").result()
    print(f"view created: {VIEW}")


def export_region(client, region, outdir):
    cols = ", ".join(f"`{c}`" for c in SUBMISSION_COLUMNS)
    sql = f"select {cols} from `{VIEW}` where region = '{region}'"
    rows = list(client.query(sql).result())
    path = Path(outdir) / f"NJ_Student_Course_Submission_{region}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(SUBMISSION_COLUMNS)
        for row in rows:
            writer.writerow(
                ["" if row[c] is None else str(row[c]) for c in SUBMISSION_COLUMNS]
            )
    print(f"  {region}: {len(rows)} rows -> {path}")
    return len(rows)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)

    client = bigquery.Client(project=PROJECT)

    print("running validation gate...")
    failures = run_checks(client)
    if failures:
        print(f"GATE FAILED ({len(failures)} issue(s)) - refusing to export:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("gate passed")

    create_view(client)
    total = sum(export_region(client, r, outdir) for r in REGIONS)
    print(f"exported {total} rows across {len(REGIONS)} region(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it against a local scratch directory**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill/docs/superpowers/nj-sleds-roster/submission
uv run --with google-cloud-bigquery python build_submission.py \
  '/workspaces/teamster/.claude/scratch/NJ SLEDS/submission-out'
```

Expected: `gate passed`, then `newark: 33150 rows`, `camden: 10343 rows`,
`exported 43493 rows across 2 region(s)`.

The output directory is inside `.claude/scratch/`, which is gitignored — the
CSVs are PII-bearing and must never be committed.

- [ ] **Step 3: Verify the written CSV formatting**

```bash
cd '/workspaces/teamster/.claude/scratch/NJ SLEDS/submission-out'
uv run python -c "
import csv
for region, expected in (('newark', 33150), ('camden', 10343)):
    with open(f'NJ_Student_Course_Submission_{region}.csv', newline='') as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == expected, (region, len(rows))
    creds = {r['CreditsEarned'] for r in rows if r['CreditsEarned']}
    assert all(len(c.split('.')[1]) == 3 for c in creds), sorted(creds)[:5]
    counties = {r['CountyCodeAssigned'] for r in rows}
    print(region, len(rows), 'counties', sorted(counties), 'ok')
"
```

Expected: row counts match, every non-blank `CreditsEarned` has three decimals,
and Camden's counties include `07` with its leading zero intact (not `7`).

- [ ] **Step 4: Write the README**

Create `README.md`:

````markdown
# NJ SLEDS Student Course Roster — grade and credit backfill

Fills `AlphaGradeEarned` and `CreditsEarned` on the loaded Student Course Roster
extract and writes a submission-ready CSV per region. Every other column passes
through byte-identical to the native PowerSchool extract.

This is a named exception to the runbook's source-fix-only cleaning model — see
the design spec for the rationale and its four narrowing constraints.

## Cycle

Run these three steps each time a fresh extract arrives.

1. Reload the extract base tables into `cokafor` (existing reload script).
1. Run the validation gate:

   ```bash
   uv run --with google-cloud-bigquery python validate_submission.py
   ```

1. Create the view and export:

   ```bash
   uv run --with google-cloud-bigquery python build_submission.py OUTDIR
   ```

`build_submission.py` runs the gate itself and refuses to export on any failure,
so step 2 is only for iterating.

## Files

| File                     | Responsibility                                       |
| ------------------------ | ---------------------------------------------------- |
| `submission_query.py`    | The SQL, the 25-column order, the legal grade domain |
| `validate_submission.py` | The pre-upload gate; `--self-test` proves it fires   |
| `build_submission.py`    | Creates the view, gates, exports per-region CSV      |

## PII

The exported CSVs carry names, dates of birth, and state IDs. Write them to
`.claude/scratch/` (gitignored), hand them only to the state-access uploader,
and never commit them or paste row-level values anywhere external.

## Known blocker outside this scope

The CDS defect is still live: 20,652 of 43,493 rows carry a bad County or School
code, including every Camden row. The fix is the one-pass School Setup change on
3 Newark and 5 Camden schools. A clean grade backfill does not make the file
submittable on its own.
````

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/superpowers/nj-sleds-roster/submission/build_submission.py \
  docs/superpowers/nj-sleds-roster/submission/README.md </dev/null
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill add \
  docs/superpowers/nj-sleds-roster/submission/build_submission.py \
  docs/superpowers/nj-sleds-roster/submission/README.md
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-nj-sleds-grade-backfill commit \
  -m 'feat(nj-sleds): submission view builder and CSV export (Refs #4630)'
```

---

## Post-implementation

Once all six tasks pass, report to the user:

1. The final gate output and the exported row counts.
1. Any residue from `check_in_scope_rows_have_grades` — the rows that have no
   grade from either source, as an aggregate count per region and band. These
   need a human decision before upload.
1. A reminder that the CDS blocker still gates submission.

Then open a PR using `.github/pull_request_template.md`, with `Refs #4630` in
the body. Aggregate counts only — no row-level values.

Resolved during planning, and recorded here so the spec's open items can be
closed: `pgfinalgrades` has no `academic_year` column and must be scoped by
`enddate`; its `Y1` term is unused after 2018; and
`base_powerschool__final_grades` cannot serve this submission because it filters
to `current_academic_year`, which has already advanced to 2026.

Still open from the spec and **not** addressed by this plan: verifying the
exported CSV matches the native file's quoting, line endings, and encoding
against what NJSLEDS accepts (the reload scripts read native files with
`utf-8-sig`, implying a BOM); confirming Camden's expected school code; and
diffing handbook v1.4 against the revision the runbook's check 9 encodes.
