# NJ SLEDS Course Roster Runbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-sufficient intern runbook plus a validated BigQuery
helper-query pack that systematizes the annual NJ SLEDS Staff and Student Course
Roster submissions for Newark and Camden.

**Architecture:** BigQuery is the diagnostic engine; PowerSchool is where fixes
land (source-fix only). The intern loads the PS extracts and reference data into
the `cokafor` dataset, runs documented SQL by hand in the BigQuery console,
tracks defects in Google Sheets, and fixes the source in PowerSchool — looping
until the regenerated extract is clean. Claude is an optional accelerant, never
on the critical path.

**Tech Stack:** BigQuery (console SQL + `bq` CLI for loads), Python
(`uv run --with openpyxl` for two one-time file-prep scripts), Google Sheets,
Markdown.

**Spec:**
`docs/superpowers/specs/2026-06-29-nj-sleds-course-roster-runbook-design.md`

> **Testing note (adaptation):** The deliverables are audit SQL and a runbook,
> not application code, so the TDD cycle is adapted: for each query the "test"
> is a **validation run against the loaded extracts** — it must execute without
> error and catch the known sample defects (e.g., the student extract's blank
> `CountyCodeAssigned` and `SchoolCodeAssigned` = `732`). Each query is written,
> run, confirmed, then embedded into the runbook with its plain-English
> explanation.

## Global Constraints

- **Source-fix only.** Never rewrite or post-filter the extract CSV. The handoff
  artifact is the regenerated native PowerSchool extract. Audit queries are
  read-only diagnostics.
- **Human-driven, Claude-optional.** Every step must be executable in the
  BigQuery console + Sheets with zero Claude access. No step may depend on a
  Claude surface.
- **PII stays in-tenant.** Row-level data with names/DOB/IDs lives only in
  BigQuery (`cokafor`) and Google Sheets. **Drop `SocialSecurityNumber` at
  load** as hygiene — NJSLEDS masks its values in the export, so it is not a
  live-PII concern, but the audit never needs it and the loaded table stays
  scoped to the audit columns. The cowork project gets de-identified
  categories/counts only.
- **Dataset:** all loaded tables and views live in `teamster-332318.cokafor`,
  reading `kipptaf_powerschool.*` read-only.
- **Load everything as `STRING`.** Autodetect would coerce codes to integers and
  strip mandatory leading zeros (`07`, `035`, `965`). Every loaded column is
  `STRING`.
- **CDS literal (exact-match per region):** Newark = `80` / `7325` / `965`;
  Camden = `07` / `1799` / `111`.
- **SCED validity** comes from `cokafor.ref_sced_codes` (built from
  `NJSLEDS_SCED-Course-Codes.xlsx`); prior-to-secondary codes are credit-free,
  secondary codes carry credit.
- **Combination-error predictor** diffs the staff extract against
  `cokafor.ref_state_staff` on `LocalStaffIdentifier`, `StaffMemberIdentifier`,
  `FirstName`, `LastName`, `DateOfBirth`.
- **Markdown:** every fenced block names a language; headings increment by one;
  identifiers in prose are backticked.

---

## File Structure

- `docs/superpowers/nj-sleds-roster/runbook.md` — the deliverable runbook;
  embeds the full query pack (each check as a `sql` block with explanation,
  how-to-run, and what-to-do-with-results), the Sheets templates, the compliance
  handoff protocol, the timeline, and intern onboarding. Built incrementally by
  Tasks 2–8.
- `docs/superpowers/nj-sleds-roster/setup/build_ref_sced_codes.py` — converts
  the two SCED xlsx sheets into one flat `ref_sced_codes.csv`.
- `docs/superpowers/nj-sleds-roster/setup/build_ref_state_staff.py` — projects
  the Staff Management export down to the audit columns, **excluding SSN**.
- Loaded BigQuery tables (not committed): `cokafor.stg_staff_extract`,
  `cokafor.stg_student_extract`, `cokafor.ref_sced_codes`,
  `cokafor.ref_state_staff`.

Input files live under `.claude/scratch/NJ SLEDS/` (gitignored); scripts take
input/output paths as arguments so no PII-bearing file is committed.

---

### Task 1: Load reference and extract tables into `cokafor`

**Files:**

- Create: `docs/superpowers/nj-sleds-roster/setup/build_ref_sced_codes.py`
- Create: `docs/superpowers/nj-sleds-roster/setup/build_ref_state_staff.py`
- Create (output, not committed): `cokafor.stg_staff_extract`,
  `cokafor.stg_student_extract`, `cokafor.ref_sced_codes`,
  `cokafor.ref_state_staff`

**Interfaces:**

- Produces: four `STRING`-typed BigQuery tables in `cokafor`. Column names match
  the source headers exactly — staff/student extract headers, plus
  `ref_sced_codes(sced_level, sced_code, subject_area, course_identifier, subject_area_name, sced_course_name)`
  and
  `ref_state_staff(LocalStaffIdentifier, StaffMemberIdentifier, FirstName, MiddleName, LastName, DateofBirth, CountyCodeAssigned1..6, DistrictCodeAssigned1..6, SchoolCodeAssigned1..6)`.

- [ ] **Step 1: Write the SCED conversion script**

```python
# docs/superpowers/nj-sleds-roster/setup/build_ref_sced_codes.py
"""Flatten the NJSLEDS SCED xlsx (two code sheets) into one CSV for BigQuery."""

import csv
import sys
from pathlib import Path

import openpyxl

SHEETS = {
    "Prior-to-Secondary Codes": "prior_to_secondary",
    "Secondary Codes": "secondary",
}
HEADER_ROW = 5  # codes start on row 6; row 5 is the header


def main(xlsx_path: str, out_path: str) -> None:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    rows: list[tuple[str, ...]] = []
    for sheet_name, level in SHEETS.items():
        ws = wb[sheet_name]
        for r in ws.iter_rows(min_row=HEADER_ROW + 1, values_only=True):
            sced_code, subject_area, course_identifier = r[0], r[1], r[2]
            if subject_area is None or course_identifier is None:
                continue
            rows.append(
                (
                    level,
                    str(sced_code).strip(),
                    str(subject_area).strip().zfill(2),
                    str(course_identifier).strip().zfill(3),
                    str(r[3] or "").strip(),
                    str(r[4] or "").strip(),
                )
            )
    out = Path(out_path)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "sced_level",
                "sced_code",
                "subject_area",
                "course_identifier",
                "subject_area_name",
                "sced_course_name",
            ]
        )
        writer.writerows(rows)
    print(f"wrote {len(rows)} SCED rows to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

- [ ] **Step 2: Run the SCED script and verify row count**

Run:

```bash
cd /workspaces/teamster
uv run --with openpyxl python \
  docs/superpowers/nj-sleds-roster/setup/build_ref_sced_codes.py \
  ".claude/scratch/NJ SLEDS/CRS docs/NJSLEDS_SCED-Course-Codes.xlsx" \
  ".claude/scratch/NJ SLEDS/ref_sced_codes.csv"
```

Expected: prints `wrote <N> SCED rows` where N is roughly 600
(prior-to-secondary) plus ~1,460 (secondary); `head -3` of the CSV shows
`prior_to_secondary` rows with 2-digit `subject_area` and 3-digit
`course_identifier` (leading zeros intact).

- [ ] **Step 3: Write the Staff Management projection script (drops SSN)**

```python
# docs/superpowers/nj-sleds-roster/setup/build_ref_state_staff.py
"""Project the NJ SLEDS Staff Management export down to audit columns only.

Keeps only the IDs/names/DOB/CDS slots the roster audit needs. The export's
SocialSecurityNumber column (NJSLEDS-masked, so not live PII) and all
HR/compensation fields are excluded as hygiene, not as a PII safeguard.
"""

import csv
import sys
from pathlib import Path

KEEP = [
    "LocalStaffIdentifier",
    "StaffMemberIdentifier",
    "FirstName",
    "MiddleName",
    "LastName",
    "DateofBirth",
    *[f"CountyCodeAssigned{i}" for i in range(1, 7)],
    *[f"DistrictCodeAssigned{i}" for i in range(1, 7)],
    *[f"SchoolCodeAssigned{i}" for i in range(1, 7)],
]


def main(in_path: str, out_path: str) -> None:
    with Path(in_path).open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in KEEP if c not in reader.fieldnames]
        if missing:
            raise SystemExit(f"export is missing expected columns: {missing}")
        count = 0
        with Path(out_path).open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=KEEP, extrasaction="ignore")
            writer.writeheader()
            for row in reader:
                writer.writerow({c: row[c] for c in KEEP})
                count += 1
    print(f"wrote {count} staff rows ({len(KEEP)} cols, no SSN) to {out_path}")
```

- [ ] **Step 4: Run the Staff Management script and verify no SSN column**

Run:

```bash
cd /workspaces/teamster
uv run python \
  docs/superpowers/nj-sleds-roster/setup/build_ref_state_staff.py \
  ".claude/scratch/NJ SLEDS/CRS docs/Export- Staff Management Submission.csv" \
  ".claude/scratch/NJ SLEDS/ref_state_staff.csv"
head -1 ".claude/scratch/NJ SLEDS/ref_state_staff.csv"
```

Expected: prints `wrote 1053 staff rows (24 cols, no SSN)`; the header line
contains no `SocialSecurityNumber`.

- [ ] **Step 5: Load all four tables as STRING into `cokafor`**

Run (the `bq` binary is at `/usr/local/share/google-cloud-sdk/bin/bq`; stable
copies avoid the spaces in the source filenames):

```bash
cd "/workspaces/teamster/.claude/scratch/NJ SLEDS"
cp "NJ_Staff_Course_Submission (21).csv" staff_extract.csv
cp "NJ_Student_Course_Submission (13).csv" student_extract.csv
BQ=/usr/local/share/google-cloud-sdk/bin/bq

STAFF="LocalStaffIdentifier:STRING,StaffMemberIdentifier:STRING,FirstName:STRING,LastName:STRING,DateOfBirth:STRING,CountyCodeAssigned:STRING,DistrictCodeAssigned:STRING,SchoolCodeAssigned:STRING,SectionEntryDate:STRING,SectionExitDate:STRING,SubjectArea:STRING,CourseIdentifier:STRING,CourseLevel:STRING,GradeSpan:STRING,AvailableCredit:STRING,CourseSequence:STRING,LocalCourseTitle:STRING,LocalCourseCode:STRING,LocalSectionCode:STRING"
$BQ load --project_id=teamster-332318 --source_format=CSV --skip_leading_rows=1 \
  --replace cokafor.stg_staff_extract staff_extract.csv "$STAFF"

STUDENT="LocalIdentificationNumber:STRING,StateIdentificationNumber:STRING,FirstName:STRING,LastName:STRING,DateOfBirth:STRING,CountyCodeAssigned:STRING,DistrictCodeAssigned:STRING,SchoolCodeAssigned:STRING,SectionEntryDate:STRING,SectionExitDate:STRING,SubjectArea:STRING,CourseIdentifier:STRING,CourseLevel:STRING,GradeSpan:STRING,AvailableCredit:STRING,CourseSequence:STRING,LocalCourseTitle:STRING,LocalCourseCode:STRING,LocalSectionCode:STRING,CreditsEarned:STRING,NumericGradeEarned:STRING,AlphaGradeEarned:STRING,CompletionStatus:STRING,CourseType:STRING,DualInstitution:STRING"
$BQ load --project_id=teamster-332318 --source_format=CSV --skip_leading_rows=1 \
  --replace cokafor.stg_student_extract student_extract.csv "$STUDENT"

$BQ load --project_id=teamster-332318 --source_format=CSV --skip_leading_rows=1 \
  --autodetect --replace cokafor.ref_sced_codes ref_sced_codes.csv
$BQ load --project_id=teamster-332318 --source_format=CSV --skip_leading_rows=1 \
  --autodetect --replace cokafor.ref_state_staff ref_state_staff.csv
```

(`ref_sced_codes` / `ref_state_staff` use `--autodetect` because the prep
scripts already wrote codes as zero-padded strings.)

- [ ] **Step 6: Verify load row counts**

Run (BigQuery MCP `execute_sql`):

```sql
select 'staff' as t, count(*) as n from `teamster-332318.cokafor.stg_staff_extract`
union all select 'student', count(*) from `teamster-332318.cokafor.stg_student_extract`
union all select 'sced', count(*) from `teamster-332318.cokafor.ref_sced_codes`
union all select 'state_staff', count(*) from `teamster-332318.cokafor.ref_state_staff`;
```

Expected: `staff` = 291, `student` = 3581, `state_staff` = 1053, `sced` ≈ 2060.
Confirm a leading-zero value survived:
`select distinct CountyCodeAssigned from ...stg_student_extract` includes `''`
(blank) and `80`, not `0`/`80.0`.

- [ ] **Step 7: Commit the setup scripts**

```bash
cd /workspaces/teamster
git add docs/superpowers/nj-sleds-roster/setup/build_ref_sced_codes.py \
        docs/superpowers/nj-sleds-roster/setup/build_ref_state_staff.py
git commit -m "feat: NJ SLEDS roster reference-data prep scripts"
```

---

### Task 2: Group A — staff field-validity checks (1–6)

**Files:**

- Create: `docs/superpowers/nj-sleds-roster/runbook.md` (skeleton + Group A)

**Interfaces:**

- Consumes: `cokafor.stg_staff_extract`, `cokafor.ref_state_staff` (Task 1).
- Produces: the runbook's Group A section with six validated `sql` blocks.

- [ ] **Step 1: Create the runbook skeleton**

Create `docs/superpowers/nj-sleds-roster/runbook.md` with a title, a
one-paragraph purpose, and a `## Group A — staff field validity` heading.
(Wrapper sections — surfaces, PII, the loop, timeline — are added in Task 7.)

- [ ] **Step 2: Write and validate check 1 (missing/invalid SMID)**

```sql
select distinct
  LocalStaffIdentifier,
  StaffMemberIdentifier,
  FirstName,
  LastName,
from `teamster-332318.cokafor.stg_staff_extract`
where StaffMemberIdentifier is null
  or not regexp_contains(StaffMemberIdentifier, r'^[0-9]{8}$');
```

Run it. Expected: executes cleanly; any rows returned are staff whose SMID is
blank or not exactly 8 digits. Record the count.

- [ ] **Step 3: Write and validate check 2 (combination-error predictor)**

First confirm the DOB formats align:
`select DateofBirth from ...ref_state_staff limit 5` vs the extract's
`DateOfBirth` (`YYYYMMDD`). If the export uses a different format, normalize
both to `YYYYMMDD` in the query below.

```sql
with extract_staff as (
  select distinct
    LocalStaffIdentifier,
    StaffMemberIdentifier,
    FirstName,
    LastName,
    DateOfBirth,
  from `teamster-332318.cokafor.stg_staff_extract`
)
select
  e.LocalStaffIdentifier,
  e.StaffMemberIdentifier,
  e.FirstName,
  e.LastName,
  case
    when r.LocalStaffIdentifier is null then 'no LSID match in state'
    when e.StaffMemberIdentifier != r.StaffMemberIdentifier then 'SMID mismatch'
    when upper(e.FirstName) != upper(r.FirstName) then 'first name mismatch'
    when upper(e.LastName) != upper(r.LastName) then 'last name mismatch'
    when e.DateOfBirth != r.DateofBirth then 'DOB mismatch'
  end as mismatch_reason,
from extract_staff as e
left join `teamster-332318.cokafor.ref_state_staff` as r
  on e.LocalStaffIdentifier = r.LocalStaffIdentifier
where r.LocalStaffIdentifier is null
  or e.StaffMemberIdentifier != r.StaffMemberIdentifier
  or upper(e.FirstName) != upper(r.FirstName)
  or upper(e.LastName) != upper(r.LastName)
  or e.DateOfBirth != r.DateofBirth;
```

Run it. Expected: executes cleanly; returns one row per staff member whose
five-field tuple does not match the state export, each tagged with the first
failing field. This is the spine check — eyeball a few rows to confirm the
`mismatch_reason` is sensible.

- [ ] **Step 4: Write and validate check 3 (duplicate LSID)**

```sql
select
  LocalStaffIdentifier,
  count(distinct format('%t|%t|%t', StaffMemberIdentifier, FirstName, LastName))
    as distinct_people,
from `teamster-332318.cokafor.stg_staff_extract`
group by LocalStaffIdentifier
having distinct_people > 1;
```

Run it. Expected: clean execution; rows (if any) are LSIDs shared by more than
one person.

- [ ] **Step 5: Write and validate check 4 (name rule violations)**

```sql
select distinct
  LocalStaffIdentifier,
  FirstName,
  LastName,
from `teamster-332318.cokafor.stg_staff_extract`
where FirstName is null
  or LastName is null
  or regexp_contains(FirstName, r"[^A-Za-z '\-]")
  or regexp_contains(LastName, r"[^A-Za-z '\-]");
```

Run it. Expected: flags names containing periods, digits, or other disallowed
characters (apostrophe, hyphen, space allowed).

- [ ] **Step 6: Write and validate check 5 (date validity)**

```sql
select distinct
  LocalSectionCode,
  StaffMemberIdentifier,
  SectionEntryDate,
  SectionExitDate,
from `teamster-332318.cokafor.stg_staff_extract`
where not regexp_contains(SectionEntryDate, r'^[0-9]{8}$')
  or SectionEntryDate < '20250701'
  or SectionEntryDate > '20260630'
  or (
    SectionExitDate is not null
    and SectionExitDate not in ('', '00000000')
    and (
      not regexp_contains(SectionExitDate, r'^[0-9]{8}$')
      or SectionExitDate < SectionEntryDate
    )
  );
```

Run it. Expected: clean execution. (The `20250701`/`20260630` window is the SY
2025-26 bracket; the runbook prose tells the intern to set it to the actual
first and last instructional days.)

- [ ] **Step 7: Write and validate check 6 (CDS validity)**

```sql
select
  CountyCodeAssigned,
  DistrictCodeAssigned,
  SchoolCodeAssigned,
  count(*) as rows,
from `teamster-332318.cokafor.stg_staff_extract`
group by 1, 2, 3
having not (
  (CountyCodeAssigned = '80' and DistrictCodeAssigned = '7325'
    and SchoolCodeAssigned = '965')
  or (CountyCodeAssigned = '07' and DistrictCodeAssigned = '1799'
    and SchoolCodeAssigned = '111')
);
```

Run it. Expected: for the Newark staff sample, ideally zero rows (all
`80/7325/965`); any returned combo is off-spec.

- [ ] **Step 8: Write the Group A runbook prose and commit**

For each check add a short "what it catches / why it errors / how to fix / who
owns it" note above its `sql` block, then:

```bash
cd /workspaces/teamster
git add docs/superpowers/nj-sleds-roster/runbook.md
git commit -m "docs: NJ SLEDS runbook Group A staff field-validity checks"
```

---

### Task 3: Group B — course/section SCED validity (7–10)

**Files:**

- Modify: `docs/superpowers/nj-sleds-roster/runbook.md`

**Interfaces:**

- Consumes: `cokafor.stg_staff_extract`, `cokafor.ref_sced_codes`.
- Produces: the runbook's Group B section with four validated `sql` blocks.
  Group B queries run against **both** extracts; the runbook notes to swap
  `stg_staff_extract` for `stg_student_extract`.

- [ ] **Step 1: Write and validate check 7 (missing SCED codes)**

```sql
select distinct
  SubjectArea,
  CourseIdentifier,
  CourseLevel,
  LocalCourseCode,
  LocalCourseTitle,
from `teamster-332318.cokafor.stg_staff_extract`
where SubjectArea is null or SubjectArea = ''
  or CourseIdentifier is null or CourseIdentifier = ''
  or CourseLevel is null or CourseLevel = '';
```

Run it. Expected: clean execution; rows are courses/sections missing a required
SCED field.

- [ ] **Step 2: Write and validate check 8 (invalid SCED codes)**

```sql
select distinct
  e.SubjectArea,
  e.CourseIdentifier,
  e.LocalCourseCode,
  e.LocalCourseTitle,
from `teamster-332318.cokafor.stg_staff_extract` as e
left join `teamster-332318.cokafor.ref_sced_codes` as r
  on e.SubjectArea = r.subject_area
  and e.CourseIdentifier = r.course_identifier
where r.subject_area is null
  and e.SubjectArea is not null
  and e.SubjectArea != '';
```

Run it. Expected: clean execution; rows are `SubjectArea` + `CourseIdentifier`
pairs absent from the SCED master list. Sanity-check that a known-good pair from
the sample (e.g., `51`/`033`) does **not** appear.

- [ ] **Step 3: Write and validate check 9 (prior-to-secondary vs secondary
      consistency)**

```sql
select distinct
  e.LocalCourseCode,
  e.SubjectArea,
  e.CourseIdentifier,
  e.AvailableCredit,
  e.GradeSpan,
  r.sced_level,
  case
    when r.sced_level = 'secondary'
      and (e.AvailableCredit is null or e.AvailableCredit = ''
        or safe_cast(e.AvailableCredit as float64) = 0)
      then 'secondary code but no credit'
    when r.sced_level = 'secondary'
      and e.GradeSpan is not null and e.GradeSpan != ''
      then 'secondary code but GradeSpan populated'
    when r.sced_level = 'prior_to_secondary'
      and safe_cast(e.AvailableCredit as float64) > 0
      then 'prior-to-secondary code but has credit'
    when r.sced_level = 'prior_to_secondary'
      and (e.GradeSpan is null or e.GradeSpan = '')
      then 'prior-to-secondary code but GradeSpan blank'
  end as inconsistency,
from `teamster-332318.cokafor.stg_staff_extract` as e
left join `teamster-332318.cokafor.ref_sced_codes` as r
  on e.SubjectArea = r.subject_area
  and e.CourseIdentifier = r.course_identifier
qualify inconsistency is not null;
```

Run it. Expected: clean execution; each returned row names the specific
credit/level/grade-span contradiction.

- [ ] **Step 4: Write and validate check 10 (domain checks)**

```sql
select distinct
  LocalCourseCode,
  CourseLevel,
  CourseSequence,
from `teamster-332318.cokafor.stg_staff_extract`
where CourseLevel not in ('B', 'G', 'E', 'H', 'X')
  or not regexp_contains(CourseSequence, r'^[1-9][1-9]$')
  or cast(substr(CourseSequence, 1, 1) as int64)
    > cast(substr(CourseSequence, 2, 1) as int64);
```

Run it. Expected: clean execution; flags bad `CourseLevel` values and
`CourseSequence` values outside `11`–`99` or with first digit > second.

- [ ] **Step 5: Write the Group B prose and commit**

Add the per-check notes (and the "run against the student extract too"
instruction), then:

```bash
cd /workspaces/teamster
git add docs/superpowers/nj-sleds-roster/runbook.md
git commit -m "docs: NJ SLEDS runbook Group B SCED-validity checks"
```

---

### Task 4: Group C — student field validity (11–12)

**Files:**

- Modify: `docs/superpowers/nj-sleds-roster/runbook.md`

**Interfaces:**

- Consumes: `cokafor.stg_student_extract`.
- Produces: the runbook's Group C section.

- [ ] **Step 1: Write and validate check 11 (missing/invalid SID)**

```sql
select distinct
  LocalIdentificationNumber,
  StateIdentificationNumber,
  FirstName,
  LastName,
from `teamster-332318.cokafor.stg_student_extract`
where StateIdentificationNumber is null
  or StateIdentificationNumber = ''
  or not regexp_contains(StateIdentificationNumber, r'^[0-9]{10}$');
```

Run it. Expected: clean execution; rows are students missing a 10-digit SID.

- [ ] **Step 2: Write and validate check 12 (student CDS — known defect)**

```sql
select
  CountyCodeAssigned,
  DistrictCodeAssigned,
  SchoolCodeAssigned,
  count(*) as rows,
from `teamster-332318.cokafor.stg_student_extract`
group by 1, 2, 3
having not (
  (CountyCodeAssigned = '80' and DistrictCodeAssigned = '7325'
    and SchoolCodeAssigned = '965')
  or (CountyCodeAssigned = '07' and DistrictCodeAssigned = '1799'
    and SchoolCodeAssigned = '111')
);
```

Run it. **Expected: returns at least the known defect** — rows with blank
`CountyCodeAssigned` and `SchoolCodeAssigned` = `732`. This confirms the check
works. The runbook note tells the intern to also run checks 7–10 against
`stg_student_extract`, and that the `732` root cause must be traced in the
loaded extract / PowerSchool (the `Alternate_School_Number` fallback hypothesis
is ruled out — see the spec).

- [ ] **Step 3: Commit**

```bash
cd /workspaces/teamster
git add docs/superpowers/nj-sleds-roster/runbook.md
git commit -m "docs: NJ SLEDS runbook Group C student field-validity checks"
```

---

### Task 5: Group D — cross-extract parity (13–15)

**Files:**

- Modify: `docs/superpowers/nj-sleds-roster/runbook.md`

**Interfaces:**

- Consumes: both extracts.
- Produces: the runbook's Group D section.

- [ ] **Step 1: Write and validate check 13 (sections with staff but no
      students)**

```sql
select distinct
  st.LocalSectionCode,
  st.LocalCourseCode,
  st.LocalCourseTitle,
  st.StaffMemberIdentifier,
from `teamster-332318.cokafor.stg_staff_extract` as st
left join (
  select distinct LocalSectionCode
  from `teamster-332318.cokafor.stg_student_extract`
) as sd
  on st.LocalSectionCode = sd.LocalSectionCode
where sd.LocalSectionCode is null;
```

Run it. Expected: clean execution; rows are teacher-section records with no
matching student rows (the PowerSchool "section with no students" junk).

- [ ] **Step 2: Write and validate check 14 (students but no 100%-allocated
      teacher)**

```sql
select
  sd.LocalSectionCode,
  any_value(sd.LocalCourseTitle) as course_title,
  count(distinct sd.LocalIdentificationNumber) as students,
from `teamster-332318.cokafor.stg_student_extract` as sd
left join (
  select distinct LocalSectionCode
  from `teamster-332318.cokafor.stg_staff_extract`
) as st
  on sd.LocalSectionCode = st.LocalSectionCode
where st.LocalSectionCode is null
group by sd.LocalSectionCode;
```

Run it. Expected: clean execution; rows are sections with enrolled students but
no teacher in the staff extract.

- [ ] **Step 3: Write and validate check 15 (section parity summary)**

```sql
select
  coalesce(a.LocalSectionCode, b.LocalSectionCode) as section,
  a.LocalSectionCode is not null as in_staff_extract,
  b.LocalSectionCode is not null as in_student_extract,
from (
  select distinct LocalSectionCode
  from `teamster-332318.cokafor.stg_staff_extract`
) as a
full outer join (
  select distinct LocalSectionCode
  from `teamster-332318.cokafor.stg_student_extract`
) as b
  on a.LocalSectionCode = b.LocalSectionCode
where a.LocalSectionCode is null or b.LocalSectionCode is null;
```

Run it. Expected: clean execution; the combined one-sided-section list (the
union of checks 13 and 14, with which side is missing).

- [ ] **Step 4: Commit**

```bash
cd /workspaces/teamster
git add docs/superpowers/nj-sleds-roster/runbook.md
git commit -m "docs: NJ SLEDS runbook Group D cross-extract parity checks"
```

---

### Task 6: Group E rollup (16) + grade-mapping one-time check

**Files:**

- Modify: `docs/superpowers/nj-sleds-roster/runbook.md`

**Interfaces:**

- Consumes: all prior checks.
- Produces: the convergence-rollup section and the one-time grade-mapping note.

- [ ] **Step 1: Write and validate check 16 (defect-count rollup)**

```sql
select 'A1_missing_smid' as check_name, count(*) as violations from (
  select distinct StaffMemberIdentifier
  from `teamster-332318.cokafor.stg_staff_extract`
  where StaffMemberIdentifier is null
    or not regexp_contains(StaffMemberIdentifier, r'^[0-9]{8}$')
)
union all
select 'C12_student_cds', count(*) from (
  select 1
  from `teamster-332318.cokafor.stg_student_extract`
  where not (
    (CountyCodeAssigned = '80' and DistrictCodeAssigned = '7325'
      and SchoolCodeAssigned = '965')
    or (CountyCodeAssigned = '07' and DistrictCodeAssigned = '1799'
      and SchoolCodeAssigned = '111')
  )
)
order by check_name;
```

Run it. Expected: clean execution; one row per check with its violation count.
The runbook note instructs the intern to extend this `union all` with the
remaining checks (the same `where` clauses already written above) and to re-run
it each loop to watch totals trend to zero. This is the de-identified artifact
(counts only) that feeds the cowork project.

- [ ] **Step 2: Write the grade-mapping one-time-check note**

Add a short subsection: the sample student extract has blank grade fields
(`NumericGradeEarned` / `AlphaGradeEarned` / `CompletionStatus`), consistent
with a mid-year extract, so grade-mapping gaps are likely N/A for KTAF. The
one-time check is to confirm, against the Student Course Roster Handbook, that
every stored-grade code in use has an NJ Grade Scale mapping before the year-end
run. No SQL until the rule is confirmed.

- [ ] **Step 3: Commit**

```bash
cd /workspaces/teamster
git add docs/superpowers/nj-sleds-roster/runbook.md
git commit -m "docs: NJ SLEDS runbook convergence rollup + grade-mapping note"
```

---

### Task 7: Runbook wrapper — surfaces, PII, the loop, timeline, onboarding

**Files:**

- Modify: `docs/superpowers/nj-sleds-roster/runbook.md`

**Interfaces:**

- Consumes: the spec's Architecture, PII boundary, and Timeline sections.
- Produces: the finished, self-sufficient runbook.

- [ ] **Step 1: Add the front matter and "how to use this runbook"**

Open with the goal, the three surfaces (BigQuery console + Sheets is the
critical path; VS Code Claude plugin and the cowork project are optional), and
an explicit "you can do everything here with zero Claude access" statement.

- [ ] **Step 2: Add the PII rules box**

State plainly: row-level data stays in BigQuery + Sheets; never paste identified
rows into the cowork project; `SocialSecurityNumber` is dropped at load and
never appears anywhere; state error reports are PII and are triaged row-level in
the console.

- [ ] **Step 3: Add the audit loop and Phase-0 setup steps**

Embed the seven-step loop from the spec, then the Phase-0 setup: the two prep
scripts and the four `bq load` commands from Task 1 (so the intern can rebuild
the tables each cycle), with the row-count verification query.

- [ ] **Step 4: Add the Sheets templates**

Document the worklist Sheet (one tab per check group; columns: defect key,
identifying fields, `fix_owner`, `status` via data-validation dropdown of
`open / fixed-in-PS / handoff-sent / verified`, `notes`), the compliance handoff
tab (new-SMID and name/DOB items with lead-time dates), and the convergence
tracker tab (check 16 counts per loop, by district/school). Include the `QUERY`
and pivot-table tips that build the intern's spreadsheet skills.

- [ ] **Step 5: Add the timeline and roles**

Copy the dated phase table from the spec (Aug 3 deadline, Jul 27 internal
target, the Jul 27–Aug 3 contingency week) and the role definitions.

- [ ] **Step 6: Trunk-check the runbook and commit**

```bash
cd /workspaces/teamster
.trunk/tools/trunk check --force docs/superpowers/nj-sleds-roster/runbook.md
git add docs/superpowers/nj-sleds-roster/runbook.md
git commit -m "docs: NJ SLEDS runbook wrapper sections (surfaces, PII, loop, timeline)"
```

Expected: trunk reports no issues.

---

### Task 8: Cowork project setup guide

**Files:**

- Modify: `docs/superpowers/nj-sleds-roster/runbook.md`

**Interfaces:**

- Produces: a short appendix describing the shared cowork project.

- [ ] **Step 1: Write the cowork setup appendix**

Document what to load into the shared cowork project (both Handbooks, the SCED
list, this runbook, and the de-identified convergence rollup), what it is used
for (handbook Q&A, error-log triage by category/count, drafting compliance
handoff notes), and the firm boundary (rules/counts/de-identified samples only —
never identified rows; redact identifiers from state error reports before
pasting).

- [ ] **Step 2: Trunk-check and commit**

```bash
cd /workspaces/teamster
.trunk/tools/trunk check --force docs/superpowers/nj-sleds-roster/runbook.md
git add docs/superpowers/nj-sleds-roster/runbook.md
git commit -m "docs: NJ SLEDS runbook cowork-project setup appendix"
```

---

## Self-Review

**Spec coverage:**

- Decisions 1–5 → Global Constraints + Tasks 1, 7. ✔
- Reference data (`ref_sced_codes`, `ref_state_staff`, two extracts, SSN drop) →
  Task 1. ✔
- Audit taxonomy checks 1–16 → Tasks 2–6. ✔
- Grade-mapping one-time check → Task 6 Step 2. ✔
- Three surfaces, PII boundary, loop → Task 7. ✔
- Deliverables: runbook (Tasks 2–8), query pack (embedded, Tasks 2–6), reference
  tables (Task 1), worklist + handoff + convergence Sheets (Task 7 Step 4),
  cowork project (Task 8). ✔
- Timeline/roles → Task 7 Step 5. ✔

**Open items carried into execution (from the spec):** trace the `732` root
cause in the loaded extract; confirm the `ref_state_staff` DOB format and join
keys (Task 3 Step 3 / Task 1); confirm student-side rules and the grade-mapping
rule against the Student Course Roster Handbook.

**Placeholder scan:** every code step has complete content; remaining "confirm
against the Handbook" items are genuine open questions flagged in the spec, not
plan placeholders.

**Type consistency:** column names match the loaded-table schemas defined in
Task 1; `ref_state_staff.DateofBirth` (lowercase `o`) vs the extract's
`DateOfBirth` is called out explicitly in Task 3 Step 3 and check 2.
