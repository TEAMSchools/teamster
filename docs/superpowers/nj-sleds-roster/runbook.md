# NJ SLEDS Course Roster Submission — Runbook

This runbook guides a KTAF data team member through the end-to-end quality
checks required before submitting the NJ SLEDS course roster file. It is
organized into groups that mirror the submission pipeline: Group A validates
staff identity fields in the extract against the state reference file; later
groups cover student enrollment, course metadata, and final submission steps.
Run each group's checks in order, resolve all flagged rows, and document
dispositions before moving to the next group.

## How to use this runbook

**Goal:** Produce a clean Staff Course Roster and Student Course Roster extract
for Newark and Camden that passes NJ SLEDS validation without any
post-processing of the CSV files. Every defect is fixed at the source in
PowerSchool so the regenerated native extract comes out clean.

### Three surfaces

The work spans three surfaces. Only the first is required.

1. **BigQuery console + Google Sheets — the critical path.** Load the extracts
   into `cokafor`, run the documented SQL by hand in the
   [BigQuery console](https://console.cloud.google.com/bigquery), build
   worklists in Sheets. You can execute this entire runbook with zero Claude
   access. All row-level data stays in-tenant on these two surfaces.

2. **VS Code Claude Code plugin — optional accelerant.** Available to help draft
   or debug a query when the intern wants it, but never required; the documented
   SQL is always the fallback. This is the only governed AI-plus-BigQuery path:
   the BigQuery console is not reachable from Claude Desktop.

3. **Shared cowork project (claude.ai / Desktop) — optional accelerant.** Loaded
   with both Handbooks, the SCED list, the runbook, and a de-identified
   error/issue catalog. Useful for handbook Q&A, error-log triage by category
   and count, drafting compliance-team handoff notes, and persisting
   institutional knowledge. Shareable with the compliance team and the
   state-access uploader. **Never paste identified rows here** — counts and
   categories only.

You can do everything in this runbook with zero Claude access. Claude is an
optional accelerant; no step may depend on a Claude surface that could hit a
usage limit and stall progress.

## PII rules

This work is PII-dense: resolving a staff combination error requires name +
DOB + SMID together; the student side carries SID + name + DOB.

- **Row-level worklists with real names, DOBs, and IDs stay in BigQuery
  (`cokafor`) and Google Sheets** (in-tenant) only. Never copy identified rows
  to the cowork project, a chat, a commit, or any other external surface.
- **The cowork project works on rules, error categories, counts, and
  de-identified samples only.** The defect-count rollup (check 16) is the only
  artifact from this runbook that goes into the cowork project — counts only, no
  PII.
- **State error reports are PII.** The state's returned error reports name
  records by SID, SMID, or name. Triage them row-level in the BigQuery console
  or VS Code. Only the de-identified taxonomy (error type, count, which query
  catches it) goes into the cowork project.
- **`SocialSecurityNumber` is never loaded.** The Staff Management export
  includes a `SocialSecurityNumber` column, but NJSLEDS masks its values in the
  export so it is not a live-PII concern. The `build_ref_state_staff.py` prep
  script drops it at load as hygiene — the audit never needs it, and the loaded
  `ref_state_staff` table contains no SSN column.

## The audit loop

Source-fix-only means this is an iterative loop, not a one-pass cleanup. A
typical submission requires two to four loops before the extract is clean.

```text
1. PS admin generates Staff + Student Course Roster extracts (Camden, Newark).
2. Intern loads both CSVs into BigQuery (cokafor staging tables); also load the
   state Staff Management / SMID export if compliance can provide it.
3. Intern runs the helper-query pack -> defect worklists (Google Sheets).
4. Intern fixes what they own in PowerSchool:
     - SCED codes (S_NJ_CRS_X / S_NJ_SEC_X)
     - staff state-ID override fields + SMID entry (S_NJ_USR_X)
     - duplicate / orphan section + schedule cleanup
5. Items the intern cannot own -> compliance-team handoff sheet:
     - generate NEW state SMIDs for new staff
     - push name/DOB changes into Staff Management / state SIS
6. Re-extract -> re-load -> re-run pack -> defects trend toward zero.
7. Clean extract handed to the state-access uploader; errors returned -> step 3.
```

Check 16 (defect-count rollup) is the de-identified artifact that shows
progress. Paste the check-16 output into the convergence tracker tab each loop
so stakeholders can watch totals trend toward zero without seeing any identified
data.

## Phase 0 — setup

Run these steps once before the first loop (and again each time you receive a
fresh extract to audit).

### Step 1 — build the reference CSVs

Run the two prep scripts from the project root. Both scripts take input and
output paths as arguments; no PII-bearing file is committed to the repo.

```bash
cd /workspaces/teamster

# Build the SCED reference CSV from the NJSLEDS SCED xlsx workbook.
uv run --with openpyxl python \
  docs/superpowers/nj-sleds-roster/setup/build_ref_sced_codes.py \
  ".claude/scratch/NJ SLEDS/CRS docs/NJSLEDS_SCED-Course-Codes.xlsx" \
  ".claude/scratch/NJ SLEDS/ref_sced_codes.csv"

# Project the Staff Management export down to audit columns, dropping SSN.
uv run python \
  docs/superpowers/nj-sleds-roster/setup/build_ref_state_staff.py \
  ".claude/scratch/NJ SLEDS/CRS docs/Export- Staff Management Submission.csv" \
  ".claude/scratch/NJ SLEDS/ref_state_staff.csv"
```

Expected output:

- `build_ref_sced_codes.py`: prints `wrote <N> SCED rows` where N is roughly
  2,060 (approximately 600 prior-to-secondary plus 1,460 secondary).
- `build_ref_state_staff.py`: prints `wrote 1053 staff rows (24 cols, no SSN)`.
  Confirm the output header contains no `SocialSecurityNumber` column.

### Step 2 — load all four tables into BigQuery

All four tables use **explicit STRING schemas**. Do not use `--autodetect` for
any table, including the reference tables: autodetect re-coerces zero-padded
`subject_area`, `course_identifier`, and CDS codes to `INT64` and strips leading
zeros, breaking the joins in checks 2 and 8.

```bash
cd "/workspaces/teamster/.claude/scratch/NJ SLEDS"

# Stable filenames avoid the spaces in the original extract filenames.
cp "NJ_Staff_Course_Submission (21).csv" staff_extract.csv
cp "NJ_Student_Course_Submission (13).csv" student_extract.csv

BQ=/usr/local/share/google-cloud-sdk/bin/bq

STAFF="LocalStaffIdentifier:STRING,StaffMemberIdentifier:STRING,FirstName:STRING,LastName:STRING,DateOfBirth:STRING,CountyCodeAssigned:STRING,DistrictCodeAssigned:STRING,SchoolCodeAssigned:STRING,SectionEntryDate:STRING,SectionExitDate:STRING,SubjectArea:STRING,CourseIdentifier:STRING,CourseLevel:STRING,GradeSpan:STRING,AvailableCredit:STRING,CourseSequence:STRING,LocalCourseTitle:STRING,LocalCourseCode:STRING,LocalSectionCode:STRING"
$BQ load --project_id=teamster-332318 --source_format=CSV --skip_leading_rows=1 \
  --replace cokafor.stg_staff_extract staff_extract.csv "$STAFF"

STUDENT="LocalIdentificationNumber:STRING,StateIdentificationNumber:STRING,FirstName:STRING,LastName:STRING,DateOfBirth:STRING,CountyCodeAssigned:STRING,DistrictCodeAssigned:STRING,SchoolCodeAssigned:STRING,SectionEntryDate:STRING,SectionExitDate:STRING,SubjectArea:STRING,CourseIdentifier:STRING,CourseLevel:STRING,GradeSpan:STRING,AvailableCredit:STRING,CourseSequence:STRING,LocalCourseTitle:STRING,LocalCourseCode:STRING,LocalSectionCode:STRING,CreditsEarned:STRING,NumericGradeEarned:STRING,AlphaGradeEarned:STRING,CompletionStatus:STRING,CourseType:STRING,DualInstitution:STRING"
$BQ load --project_id=teamster-332318 --source_format=CSV --skip_leading_rows=1 \
  --replace cokafor.stg_student_extract student_extract.csv "$STUDENT"

SCED="sced_level:STRING,sced_code:STRING,subject_area:STRING,course_identifier:STRING,subject_area_name:STRING,sced_course_name:STRING"
$BQ load --project_id=teamster-332318 --source_format=CSV --skip_leading_rows=1 \
  --replace cokafor.ref_sced_codes ref_sced_codes.csv "$SCED"

STATE="LocalStaffIdentifier:STRING,StaffMemberIdentifier:STRING,FirstName:STRING,MiddleName:STRING,LastName:STRING,DateofBirth:STRING,CountyCodeAssigned1:STRING,CountyCodeAssigned2:STRING,CountyCodeAssigned3:STRING,CountyCodeAssigned4:STRING,CountyCodeAssigned5:STRING,CountyCodeAssigned6:STRING,DistrictCodeAssigned1:STRING,DistrictCodeAssigned2:STRING,DistrictCodeAssigned3:STRING,DistrictCodeAssigned4:STRING,DistrictCodeAssigned5:STRING,DistrictCodeAssigned6:STRING,SchoolCodeAssigned1:STRING,SchoolCodeAssigned2:STRING,SchoolCodeAssigned3:STRING,SchoolCodeAssigned4:STRING,SchoolCodeAssigned5:STRING,SchoolCodeAssigned6:STRING"
$BQ load --project_id=teamster-332318 --source_format=CSV --skip_leading_rows=1 \
  --replace cokafor.ref_state_staff ref_state_staff.csv "$STATE"
```

### Step 3 — verify row counts

Run this in the BigQuery console to confirm all four tables loaded correctly:

```sql
select 'staff' as t, count(*) as n
from `teamster-332318.cokafor.stg_staff_extract`
union all select 'student', count(*)
from `teamster-332318.cokafor.stg_student_extract`
union all select 'sced', count(*)
from `teamster-332318.cokafor.ref_sced_codes`
union all select 'state_staff', count(*)
from `teamster-332318.cokafor.ref_state_staff`;
```

Expected: `staff` = 291, `student` = 3581, `state_staff` = 1053, `sced` ≈ 2060.

Also confirm leading zeros survived — run
`select distinct CountyCodeAssigned from teamster-332318.cokafor.stg_student_extract`
and verify the result contains `''` (blank) and `80`, not `0` or `80.0`. If you
see integer-looking values, the load used autodetect or a wrong schema — re-run
Step 2 with the explicit schema strings above.

## Group A — staff field validity

The six checks below catch the field-level errors most likely to cause SLEDS
rejection: missing or malformed SMIDs, identity mismatches against the state's
own staff file, duplicate local IDs, illegal name characters, out-of-window
dates, and wrong CDS codes. Run each query against `cokafor.stg_staff_extract`
(291 rows for the Newark sample) and `cokafor.ref_state_staff` (1 053 rows)
before every submission.

### Check 1 — missing or invalid SMID

**What it catches:** Staff whose `StaffMemberIdentifier` is NULL or is not
exactly 8 digits. SLEDS requires a valid 8-digit SMID on every row; a missing or
malformed SMID causes the entire staff record to reject.

**Why it happens:** New hires whose SMID has not yet been entered in the HR
system, or LSIDs stored as temp codes (e.g. `TMP00349`, `SAUDNRHRY`) that were
never resolved to a real NJ staff ID.

**How to fix:** Look up the staff member in the NJ TEACH portal or contact the
People Operations team to obtain the correct SMID. If the person is not yet
registered with the state, hold the record until registration is complete.

**Owner:** People Operations (SMID lookup); Data team (extract correction).

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

_Validation result (2025-26 Newark sample): 22 rows — staff whose SMID is NULL,
including records with temp-style LSIDs. Each must be resolved or held before
submission._

### Check 2 — combination-error predictor (spine check)

**What it catches:** Staff whose five-field identity tuple
(`LocalStaffIdentifier`, `StaffMemberIdentifier`, `FirstName`, `LastName`,
`DateOfBirth`) does not match the state's `ref_state_staff` file. SLEDS
cross-references all five fields; any mismatch causes a combination error that
blocks the roster line.

**Why it happens:** Name changes not propagated to the state file, LSIDs not yet
registered with NJ (no match at all), or data-entry discrepancies (e.g. middle
initial embedded in `FirstName`).

**How to fix:** For `no LSID match in state` rows, the staff member is not yet
in the state reference — escalate to People Operations. For name or DOB
mismatches, compare the extract value to the state value and correct whichever
source is wrong; name changes require a state-side update via NJ TEACH.

**Owner:** People Operations (state registration/corrections); Data team
(extract corrections).

**Note:** DOB fields are confirmed `YYYYMMDD` strings in both tables —
`stg_staff_extract.DateOfBirth` and `ref_state_staff.DateofBirth` — so no
normalization is needed.

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

_Validation result (2025-26 Newark sample): 17 rows — mix of
`no LSID match in state` (staff not yet registered) and name mismatches. This is
expected signal given that only 67 distinct LSIDs match the state file; the
mismatch reasons are sensible._

### Check 3 — duplicate LSID

**What it catches:** LSIDs that map to more than one distinct person
(`StaffMemberIdentifier`, `FirstName`, `LastName` triple). A shared LSID means
two staff members will collide in the roster, causing unpredictable rejects.

**Why it happens:** Data-entry error, a rehired staff member reassigned a
previously-used local ID, or a system migration that created duplicate records.

**How to fix:** Identify which record is correct (usually the active
enrollment), reassign a unique LSID to the duplicate, and update the source
system. Coordinate with HR and the SIS administrator.

**Owner:** HR / SIS administrator; Data team (extract correction).

```sql
select
  LocalStaffIdentifier,
  count(distinct format('%t|%t|%t', StaffMemberIdentifier, FirstName, LastName))
    as distinct_people,
from `teamster-332318.cokafor.stg_staff_extract`
group by LocalStaffIdentifier
having distinct_people > 1;
```

_Validation result (2025-26 Newark sample): 0 rows — no duplicate LSIDs. Clean._

### Check 4 — name rule violations

**What it catches:** `FirstName` or `LastName` values that are NULL or contain
characters outside the allowed set (letters, apostrophe, hyphen, space). SLEDS
rejects names with periods, digits, or other special characters.

**Why it happens:** Middle initials appended to `FirstName` (e.g. `Daniel R`),
suffixes embedded in `LastName`, or data imported from a system with looser name
validation.

**How to fix:** Remove the disallowed character. If a middle initial is in
`FirstName`, strip it and store only the given name. Periods after initials must
be removed. Hyphens and apostrophes are allowed and should be preserved.

**Owner:** Data team (extract correction); People Operations confirms legal name
spelling.

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

_Validation result (2025-26 Newark sample): 1 row — `St. Clair` in `LastName`,
flagged on the period (`.`). NJ SLEDS allows only letters, apostrophe, hyphen,
and space in name fields, so the abbreviation's period is the violation; the fix
is to store the name without the period (`St Clair`) in the SIS. No `FirstName`
violations were found._

### Check 5 — date validity

**What it catches:** `SectionEntryDate` values that are not 8-digit strings,
fall outside the SY 2025-26 window (`20250701`–`20260630`), or `SectionExitDate`
values that are malformed or precede the entry date.

**Why it happens:** Dates exported in a non-`YYYYMMDD` format, section
assignments carried over from a prior year, or exit dates entered before the
entry date due to data-entry error.

**How to fix:** Correct the date in the source SIS. For out-of-window entry
dates, verify whether the section assignment is truly from the current year;
prior-year records should be excluded from the extract. Update the window
constants (`20250701` / `20260630`) each year to the actual first and last
instructional days.

**Owner:** Data team (extract correction); School ops confirms section dates.

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

_Validation result (2025-26 Newark sample): 0 rows — all dates are in range and
well-formed. Clean._

### Check 6 — CDS code validity

**What it catches:** Rows whose `CountyCodeAssigned` / `DistrictCodeAssigned` /
`SchoolCodeAssigned` combination is not on the approved list for this
submission. An unexpected CDS combo means the record will be attributed to the
wrong school in the state system.

**Why it happens:** Incorrect school code in the source system, a school merger
or renaming that changed the CDS, or staff assigned to a placeholder or
administrative code instead of an instructional school.

**How to fix:** Verify the correct CDS for each flagged school in the NJDOE
school directory and correct the source system. Add new approved CDS combos to
the `having` allowlist in this query each year as needed.

**Owner:** Data team (CDS mapping); School ops confirms correct NJDOE school
codes.

**Note:** The brief's original query uses `rows` as a column alias, which is a
reserved word in BigQuery. The query below uses `row_count` instead — use this
corrected version.

```sql
select
  CountyCodeAssigned,
  DistrictCodeAssigned,
  SchoolCodeAssigned,
  count(*) as row_count,
from `teamster-332318.cokafor.stg_staff_extract`
group by 1, 2, 3
having not (
  (CountyCodeAssigned = '80' and DistrictCodeAssigned = '7325'
    and SchoolCodeAssigned = '965')
  or (CountyCodeAssigned = '07' and DistrictCodeAssigned = '1799'
    and SchoolCodeAssigned = '111')
);
```

_Validation result (2025-26 Newark sample): 1 row — `null/7325/732` with 115
rows. Two distinct defects in the same combo: `CountyCodeAssigned` is NULL (the
Newark county is `80`), and `SchoolCodeAssigned` is `732` rather than the
approved `965`. Both must be corrected in PowerSchool's state-reporting fields
before submission; trace the `732` source in the loaded extract (the
`Alternate_School_Number` fallback hypothesis is ruled out — see the spec)._

## Group B — course/section SCED validity

The four checks below validate the course and section metadata that SLEDS uses
to categorize instruction. Checks 7–10 apply to both the staff and student
extracts — run each query as written against `cokafor.stg_staff_extract` (291
rows), then re-run by swapping `stg_staff_extract` for `stg_student_extract` (3
581 rows, same SCED columns). The SCED reference table `cokafor.ref_sced_codes`
(2 069 rows) is the authoritative code list; all joins use string-typed columns
with leading zeros intact (`subject_area` is 2-digit, `course_identifier` is
3-digit) so no casting or zero-padding is needed.

### Check 7 — missing SCED codes

**What it catches:** Course/section rows where `SubjectArea`,
`CourseIdentifier`, or `CourseLevel` is NULL or blank. All three fields are
required by SLEDS; a missing value on any one of them causes the row to reject
outright.

**Why it happens:** Courses added to the SIS without a complete SCED mapping, or
sections loaded from a template where the SCED fields were never populated.
`CourseLevel` is particularly prone to being left blank when a course is flagged
as non-credit-bearing during setup.

**How to fix:** For each flagged `LocalCourseCode`, look up the correct SCED
subject area, course identifier, and level in the
[SCED manual](https://nces.ed.gov/forum/sced.asp) or the district's master
course list. Update the course record in the SIS and re-export the extract.

**Owner:** Registrar / curriculum coordinator (SCED assignment); Data team
(extract correction).

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

_Validation result (2025-26 Newark staff sample): 0 rows — all course/section
rows carry a `SubjectArea`, `CourseIdentifier`, and `CourseLevel`. Clean. Re-run
against `stg_student_extract` before submission._

### Check 8 — invalid SCED subject area / course identifier

**What it catches:** `SubjectArea` + `CourseIdentifier` pairs that do not appear
in `ref_sced_codes`. SLEDS validates against the national SCED master list; an
unrecognised pair causes the roster line to reject.

**Why it happens:** A locally-invented course code that was never mapped to a
real SCED pair, a transcription error (e.g. swapped digits), or an outdated code
that was retired in a newer SCED edition.

**How to fix:** Look up the correct `SubjectArea`/`CourseIdentifier` for the
flagged `LocalCourseTitle` in the SCED manual. If the code was recently revised,
check whether the district is using an older edition and update to the current
one. Correct the SIS and re-export.

**Owner:** Registrar / curriculum coordinator (SCED mapping); Data team (extract
correction).

**Sanity check:** The pair `51`/`033` (Physical Education — Elementary) appears
in `ref_sced_codes` and is present in the Newark extract. It does **not** appear
in the invalid list below, confirming that the join resolves correctly for
known-good codes. All 8 distinct `SubjectArea`/`CourseIdentifier` pairs in the
staff extract matched the reference table.

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

_Validation result (2025-26 Newark staff sample): 0 rows — all 8 distinct SCED
pairs in the extract match `ref_sced_codes`. Clean. Re-run against
`stg_student_extract` before submission._

### Check 9 — prior-to-secondary vs secondary level consistency

**What it catches:** Rows where the SCED level of the course
(`prior_to_secondary` or `secondary`, from `ref_sced_codes.sced_level`) is
inconsistent with the credit and grade-span fields. Secondary courses must carry
a non-zero `AvailableCredit` and must have a blank `GradeSpan`;
prior-to-secondary courses must have a zero or absent `AvailableCredit` and must
have `GradeSpan` populated. SLEDS uses these combinations to place the course in
the correct instructional tier; a mismatch causes reporting errors downstream.

**Why it happens:** A course that was reclassified between SCED levels without
updating the credit or grade-span fields, or a template that defaulted credit to
`0` for all courses regardless of level.

**How to fix:** The `inconsistency` column names the specific contradiction.
Correct the field that is wrong: update `AvailableCredit` in the SIS for
secondary courses that lack it, clear `GradeSpan` for secondary courses that
have it populated, or vice versa for prior-to-secondary courses. Re-export after
correcting the source.

**Owner:** Registrar (credit and grade-span data); Data team (extract
correction).

**Note:** The original brief's check 9 uses a `QUALIFY` clause to filter on the
`inconsistency` alias. BigQuery requires an analytic function to be present when
`QUALIFY` is used; since `inconsistency` is a scalar `CASE` expression, the
query was rewritten as a subquery with an outer `WHERE` filter. The logic is
identical.

```sql
select *
from (
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
)
where inconsistency is not null;
```

_Validation result (2025-26 Newark staff sample): 0 rows — no credit/level/
grade-span contradictions found. Clean. Re-run against `stg_student_extract`
before submission._

### Check 10 — domain checks (CourseLevel and CourseSequence)

**What it catches:** Rows where `CourseLevel` is not one of the five allowed
values (`B` Basic, `G` General, `E` Advanced/Enriched, `H` Honors, `X` Gifted),
or where `CourseSequence` is not a two-digit string in the range `11`–`99`, or
where the first digit of `CourseSequence` exceeds the second (i.e. the sequence
number of this section is greater than the total sections in the sequence, which
is logically impossible).

**Why it happens:** `CourseLevel` values may come from a free-text SIS field
where staff enter inconsistent codes (`h` instead of `H`, or `REG` instead of
`G`). `CourseSequence` errors typically arise when sections are added for a
multi-part course without following the `XY` convention (where X = part number
and Y = total parts in the sequence).

**How to fix:** For `CourseLevel` violations, map the flagged value to the
correct allowed code and update the SIS. For `CourseSequence` violations,
confirm the intended sequence with the registrar (e.g. a two-semester course
should be `12` and `22`) and update accordingly. Note that `CourseSequence` must
be a two-character string of digits — leading zeros and single-character values
both fail the pattern check.

**Owner:** Registrar (course metadata); Data team (extract correction).

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

_Validation result (2025-26 Newark staff sample): 0 rows — all `CourseLevel`
values are in the allowed set and all `CourseSequence` values are well-formed.
Clean. Re-run against `stg_student_extract` before submission._

## Group C — student field validity

The two checks below validate student-specific identity and CDS fields in
`cokafor.stg_student_extract` (3,581 rows). Check 11 flags students whose state
ID is missing or malformed; check 12 flags CDS combinations not on the approved
list. **Before running these checks, also re-run Group B checks 7–10 against
`stg_student_extract`** by swapping `stg_staff_extract` for
`stg_student_extract` in each query — the Group B intro explains the swap. All
course/section columns are present in both extracts.

### Check 11 — missing or invalid student state ID (SID)

**What it catches:** Students whose `StateIdentificationNumber` is NULL, blank,
or not exactly 10 digits. SLEDS requires a valid 10-digit numeric NJ state
student ID on every enrollment row; a missing or malformed SID causes the row to
reject.

**Why it happens:** New students enrolled mid-year before the state has issued
an ID, or IDs stored as placeholders (e.g. locally-assigned temporary numbers
that are not 10 digits). PowerSchool's `State_StudentNumber` field is the
expected source; if it is blank the extract will produce a NULL.

**How to fix:** Look up the student in the NJ Student Learning Registry (NJSLR)
or contact the state's student data helpdesk to obtain the correct 10-digit SID.
If the student is newly enrolled and the state ID is pending, hold the row until
the ID is issued. Do not substitute a local ID or truncate/pad a non-10-digit
value.

**Owner:** Registrar / school data manager (SID lookup); Data team (extract
correction).

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

_Validation result (2025-26 Newark sample): 0 rows — all 3,581 students carry a
10-digit numeric `StateIdentificationNumber`. Clean._

### Check 12 — student CDS code validity (known defect)

**What it catches:** Rows whose `CountyCodeAssigned` / `DistrictCodeAssigned` /
`SchoolCodeAssigned` combination is not on the approved list for this
submission. An unexpected CDS combo means the enrollment will be attributed to
the wrong school in the state system.

**Why it happens:** The same root cause as the staff-side CDS defect in check 6:
`SchoolCodeAssigned` is populated with `732` instead of the approved Newark code
`965`, and `CountyCodeAssigned` is NULL instead of `80`. The
`Alternate_School_Number` fallback hypothesis is ruled out — see the spec. The
source must be traced in the loaded extract and corrected in PowerSchool's
state-reporting fields.

**How to fix:** Identify which PowerSchool field populates `SchoolCodeAssigned`
in the extract and verify whether the value `732` is stored there directly or
computed. Correct the field to `965` (Newark) or `111` (Camden) for all
applicable students and re-export. Also populate `CountyCodeAssigned` with `80`
(Newark) or `07` (Camden) as appropriate. Add new approved CDS combos to the
`having` allowlist each year as schools are added or codes change.

**Owner:** Data team (CDS mapping and PowerSchool field audit); School ops
confirms correct NJDOE school codes.

**Note:** The brief's original query uses `rows` as a column alias, which is a
reserved word in BigQuery. The query below uses `row_count` instead — use this
corrected version.

**Expected result:** This check is designed to return rows. The `null/7325/732`
combination below is the known defect; its presence confirms the check is
working. Do not treat a non-zero result here as a query error — it is the signal
the check is intended to surface.

```sql
select
  CountyCodeAssigned,
  DistrictCodeAssigned,
  SchoolCodeAssigned,
  count(*) as row_count,
from `teamster-332318.cokafor.stg_student_extract`
group by 1, 2, 3
having not (
  (CountyCodeAssigned = '80' and DistrictCodeAssigned = '7325'
    and SchoolCodeAssigned = '965')
  or (CountyCodeAssigned = '07' and DistrictCodeAssigned = '1799'
    and SchoolCodeAssigned = '111')
);
```

_Validation result (2025-26 Newark sample): 1 row — `null/7325/732` with 1,475
students. This is the known defect: `CountyCodeAssigned` is NULL (should be
`80`) and `SchoolCodeAssigned` is `732` (should be `965`). Both must be
corrected in PowerSchool's state-reporting fields before submission. The
`Alternate_School_Number` fallback hypothesis is ruled out — trace the `732`
source in the loaded extract and PowerSchool directly._

## Group D — cross-extract parity

The three checks below compare the staff and student extracts against each other
using `LocalSectionCode` as the join key. A section present in only one extract
is an orphan: either a teacher is assigned to a section with no enrolled
students, or students are enrolled in a section with no teacher. Both conditions
are meaningful signal — they reflect the "noisy PowerSchool extract" problem
where phantom or misconfigured sections make it through the pull. Returning rows
from these checks is expected; the goal is to surface the orphans so they can be
traced and fixed at the source. Run all three checks before every submission.

**Source-fix-only principle:** orphan sections must be resolved in PowerSchool —
either by enrolling the missing students, assigning the missing teacher, or
removing the phantom section. Do not edit the extract file directly to mask
these gaps; doing so breaks the audit trail and may cause downstream SLEDS
reconciliation errors.

### Check 13 — sections with a staff row but no enrolled students

**What it catches:** `LocalSectionCode` values that appear in
`stg_staff_extract` (a teacher is assigned) but have no matching row in
`stg_student_extract` (no students enrolled). SLEDS will reject a teacher
assignment for a section that carries no enrollment, or the section will appear
as a zero-enrolment ghost that inflates the district's reported section count.

**Why it happens:** PowerSchool sometimes exports teacher-section assignments
for sections that were created but never populated — planning sections, dropped
electives, or sections that were merged into another code without removing the
original assignment. The "General Elective" pattern in the sample is a common
culprit.

**How to fix:** For each flagged `LocalSectionCode`, confirm in PowerSchool
whether the section genuinely has no students. If it is a phantom, inactivate
the section or remove the teacher assignment in the SIS and re-export. If
students are enrolled but missing from the extract, investigate the student pull
filter and correct it there.

**Owner:** School registrar (section enrollment); Data team (extract
verification).

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

_Validation result (2025-26 Newark sample): 14 rows across 13 distinct sections.
Section `35253` ("i-Ready Gr5") appears twice because two teachers are assigned
to it; the remaining 12 are "General Elective Gr5" sections (`SEM72250G1`) with
no enrolled students. All are staff-only orphans requiring investigation in
PowerSchool._

### Check 14 — sections with enrolled students but no teacher

**What it catches:** `LocalSectionCode` values that appear in
`stg_student_extract` (students are enrolled) but have no matching row in
`stg_staff_extract` (no teacher assigned). A section with enrolled students and
no teacher cannot be submitted to SLEDS — the state requires a staff record for
every course section that carries enrollment.

**Why it happens:** A teacher assignment was not entered in PowerSchool, the
teacher's record failed an earlier extract filter (e.g. a SMID issue from check
1 caused the row to be excluded), or the section was assigned to a substitute or
leave-coverage arrangement that the SIS does not capture as a formal assignment.

**How to fix:** For each flagged `LocalSectionCode`, identify who is teaching
the section and create or correct the teacher assignment in PowerSchool. If the
root cause is an upstream extract filter (e.g. the teacher's row was excluded
due to a SMID problem), resolve the upstream check first and re-export both
extracts together before re-running this check.

**Owner:** School registrar (teacher assignment); Data team (extract
verification).

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

_Validation result (2025-26 Newark sample): 0 rows — every section with enrolled
students has at least one teacher row in the staff extract. Clean._

### Check 15 — full-outer-join parity summary

**What it catches:** The combined view of checks 13 and 14. A full outer join
across the two extracts' distinct `LocalSectionCode` sets, filtered to only
one-sided sections, shows at a glance which sections are staff-only
(`in_staff_extract = true`, `in_student_extract = false`) and which are
student-only (`in_staff_extract = false`, `in_student_extract = true`). This is
the single query to run when you want a complete picture of cross-extract
mismatches without running checks 13 and 14 separately.

**Why it matters:** Checks 13 and 14 each catch one side of the mismatch. Check
15 is the union of both — it confirms the total count of orphan sections and
makes it easy to verify that fixes applied after checks 13 and 14 have fully
closed the gap (when check 15 returns 0 rows, the two extracts are in parity).

**How to fix:** Apply the same source-fix-only approach described in checks 13
and 14: trace each flagged section in PowerSchool and resolve the missing
enrollment or teacher assignment at the source. Re-export both extracts together
and re-run this check until it returns 0 rows.

**Owner:** School registrar (section setup); Data team (extract verification).

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

_Validation result (2025-26 Newark sample): 13 rows, all with
`in_staff_extract = true` and `in_student_extract = false`. This is the expected
result given that check 13 found 13 distinct staff-only sections and check 14
found 0 student-only sections. The 13 orphan sections must be resolved in
PowerSchool before submission._

## Group E — convergence rollup

Check 16 is a single `union all` query that collapses every individual check
into one row per check with a violation count. It is the de-identified artifact
(counts only, no PII) that feeds the cowork project tracker and the convergence
tracker: paste the output into the shared sheet each loop so stakeholders can
watch totals trend toward zero without seeing any student or staff data.

### Check 16 — defect-count rollup

**What it does:** Runs a representative subset of the Group A–D checks in a
single query, returning one row per check with its violation count. When all
counts reach zero, the extract is ready to submit.

**How to extend:** The starter below includes two checks. Before the first
convergence loop, extend the `union all` with the remaining checks by copying
the `where` clause from each individual check above:

- `A2_spine_mismatch` — check 2's left-join `where` predicate
- `A3_duplicate_lsid` — check 3's `having distinct_people > 1` subquery
- `A4_name_violations` — check 4's `regexp_contains` predicates
- `A5_date_violations` — check 5's date-range and format predicates
- `A6_staff_cds` — check 6's `having not (...)` subquery
- `B7_missing_sced_staff` — check 7 against `stg_staff_extract`
- `B7_missing_sced_student` — check 7 rerun against `stg_student_extract`
- `B8_invalid_sced_staff` — check 8 against `stg_staff_extract`
- `B8_invalid_sced_student` — check 8 rerun against `stg_student_extract`
- `B9_level_inconsistency_staff` — check 9 against `stg_staff_extract`
- `B9_level_inconsistency_student` — check 9 rerun against `stg_student_extract`
- `B10_domain_violations_staff` — check 10 against `stg_staff_extract`
- `B10_domain_violations_student` — check 10 rerun against `stg_student_extract`
- `C11_missing_sid` — check 11's `where` predicate
- `D13_staff_only_sections` — check 13's left-join
  `where sd.LocalSectionCode is null`
- `D14_student_only_sections` — check 14's left-join
  `where st.LocalSectionCode is null`

Each new block follows the same shape:
`select '<label>', count(*) from (... <where clause from the individual check> )`.

**Owner:** Data team (run at the start of each convergence loop).

```sql
select 'A1_missing_smid' as check_name, count(*) as violations
from (
  select distinct
    LocalStaffIdentifier,
    StaffMemberIdentifier,
    FirstName,
    LastName,
  from `teamster-332318.cokafor.stg_staff_extract`
  where StaffMemberIdentifier is null
    or not regexp_contains(StaffMemberIdentifier, r'^[0-9]{8}$')
)
union all
select 'C12_student_cds', count(*) as violations
from (
  select 1
  from `teamster-332318.cokafor.stg_student_extract`
  where not (
    (CountyCodeAssigned = '80' and DistrictCodeAssigned = '7325'
      and SchoolCodeAssigned = '965')
    or (CountyCodeAssigned = '07' and DistrictCodeAssigned = '1799'
      and SchoolCodeAssigned = '111')
  )
)
-- extend here: add one union all block per remaining check
order by check_name;
```

_Validation result (2025-26 Newark sample, starter rows only):_

| `check_name`      | `violations` |
| ----------------- | ------------ |
| `A1_missing_smid` | 22           |
| `C12_student_cds` | 1 475        |

_Both counts match the individual checks above, confirming the rollup logic is
correct. Extend the `union all` before the first convergence loop._

### Grade-mapping one-time check

The sample student extract has blank `NumericGradeEarned`, `AlphaGradeEarned`,
and `CompletionStatus` fields on all rows, consistent with a mid-year pull where
grades have not yet been posted. Grade-mapping gaps are therefore likely N/A for
KTAF for the current submission cycle.

**Before the year-end run**, confirm against the Student Course Roster Handbook
that every stored-grade code in use in the SIS has a corresponding NJ Grade
Scale mapping. Until that mapping is verified against the Handbook, no SQL check
is written here — the exact allowed codes and their mappings must be drawn from
the Handbook directly, not inferred from sample data. This is an open item to
revisit when posted grades are available in the extract.

## Worklist and tracker sheets

### Worklist tabs (one per check group)

Create one Google Sheet per district (Newark, Camden) with the following tab
structure. Each tab covers one check group and holds the row-level defect
worklist for that group. Row-level data stays in this Sheet; do not paste
identified rows into the cowork project.

#### Columns for every worklist tab

| Column               | Content                                                                                |
| -------------------- | -------------------------------------------------------------------------------------- |
| `defect_key`         | Stable identifier for the row (e.g. `A1-LSID-12345` — group + check + local ID)        |
| `identifying_fields` | The non-name fields needed to locate the record (LSID, SMID, `LocalSectionCode`, etc.) |
| `fix_owner`          | `intern`, `compliance`, or `data_team`                                                 |
| `status`             | Data-validation dropdown: `open`, `fixed-in-PS`, `handoff-sent`, `verified`            |
| `notes`              | Free text — what was found, what was done                                              |

Add rows by pasting the output of each individual check from the BigQuery
console. Do not paste `FirstName`, `LastName`, `DateOfBirth`, SID, or any other
direct identifier — use `LocalStaffIdentifier`, `LocalIdentificationNumber`,
`StaffMemberIdentifier`, and `LocalSectionCode` as the identifying fields.

#### QUERY tip

Use the Sheets `QUERY` function to pull subtotals without a pivot table:

```text
=QUERY(A:E, "select D, count(A) where E = 'open' group by D label D 'owner', count(A) 'open count'", 1)
```

This groups open defects by `fix_owner`. Adjust column letters to match your
sheet layout.

#### Pivot-table tip

Insert a pivot table (Insert → Pivot table) with `status` as rows and
`fix_owner` as columns to get a one-glance count matrix. Refresh it after each
loop to track progress without re-running the SQL.

### Compliance handoff tab

Add a tab named `compliance-handoff` to each district Sheet. This tab holds only
the items the intern cannot resolve — items that require state-side action by
the compliance team.

| Column               | Content                                                                      |
| -------------------- | ---------------------------------------------------------------------------- |
| `item_type`          | `new-SMID` or `name-DOB-correction`                                          |
| `identifying_fields` | `LocalStaffIdentifier` and `StaffMemberIdentifier` (no names in this column) |
| `current_value`      | What the extract holds                                                       |
| `correct_value`      | What it should be (from the HR system or the intern's investigation)         |
| `requested_by`       | Date the intern added this row                                               |
| `needed_by`          | Lead-time date — allow at least one week for the compliance team to act      |
| `status`             | `pending`, `in-progress`, `complete`                                         |

New-SMID requests are the long pole in the timeline — generate the handoff sheet
as early as possible in Phase 1 so the compliance team can start immediately.

### Convergence tracker tab

Add a tab named `convergence-tracker` to each district Sheet. Paste the output
of check 16 here at the start of each loop.

| Column       | Content                                           |
| ------------ | ------------------------------------------------- |
| `loop`       | Loop number (1, 2, 3, …)                          |
| `date`       | Date of this run                                  |
| `check_name` | From the check-16 rollup (e.g. `A1_missing_smid`) |
| `violations` | Count from the rollup                             |

This is the only tab that feeds the cowork project — it contains counts only, no
identified data. Share the tab (or a screenshot of it) with the cowork project
at the start of each state-error triage session.

To break out violations by district or school, extend check 16 to include a
`district` or `school` grouping column, then use a pivot table here with
`check_name` as rows and `district` as columns.

## Timeline and roles

### Roles

| Role                  | Who                     | Responsibilities                                                                                                                                                                                       |
| --------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Intern (`cokafor`)    | Data intern             | Runs audits; builds and maintains worklists; fixes intern-owned items in PowerSchool (SCED codes, staff state-ID override fields, SMID entry, duplicate/orphan cleanup); keeps the convergence tracker |
| Compliance team       | State-access staff      | State-side-only actions: generate new SMIDs, push name/DOB changes into Staff Management / state SIS, clear Snapshot Error/Sync/Unresolved flags                                                       |
| State-access uploader | Designated staff member | Uploads the clean extract; returns the state error report                                                                                                                                              |
| Data team / owner     | KTAF data team          | Reviews worklists; settles judgment calls; escalates blockers                                                                                                                                          |

The intern cannot access state systems. The compliance team does not touch
PowerSchool. These lanes are firm.

### Timeline

**Key dates:** the state hard deadline is Mon Aug 3. The internal target is to
finish everything — including state error resolution — by Mon Jul 27, leaving
the full Jul 27 – Aug 3 week as contingency for state-side system issues
(historically necessary to absorb state-side weirdness). Work starts the week of
Mon Jun 29.

| Phase                  | Window          | Work                                                                                                                                                                                     |
| ---------------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0 — Setup              | Jun 29 – Jul 3  | Provision access; load `ref_sced_codes` + the first Camden + Newark extracts (+ `ref_state_staff` if compliance provides it); intern SQL/Sheets onboarding; grade-mapping one-time check |
| 1 — Staff + SCED codes | Jul 6 – Jul 10  | Groups A + B; front-load the compliance handoff (new SMIDs, name/DOB) immediately — the long pole, and July vacations compress it                                                        |
| 2 — Student            | Jul 13 – Jul 17 | Group C (SID, CDS, dates); staff fixes continue in parallel                                                                                                                              |
| 3 — Parity             | Jul 15 – Jul 22 | Group D orphans/junk (overlaps Phase 2)                                                                                                                                                  |
| 4 — Converge           | by Jul 22       | Re-extract, re-run pack, defect rollup to zero, clean files to the uploader                                                                                                              |
| 5 — State errors       | Jul 22 – Jul 27 | Triage returned errors, loop until accepted — finish by the Jul 27 internal target                                                                                                       |
| Contingency            | Jul 27 – Aug 3  | Reserved buffer for state-side system issues; do not plan work here                                                                                                                      |

**Vacation navigation:** identify each role's availability up front. Schedule
the handoff-dependent items earliest — compliance-team SMID generation is the
long pole. Sequence intern-owned PowerSchool fixes so they never block waiting
on someone who is out.
