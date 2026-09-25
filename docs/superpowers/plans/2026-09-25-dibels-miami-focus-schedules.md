# Miami Focus schedules on the DIBELS dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Miami students appear on `rpt_tableau__dibels_dashboard` with ELA
teacher, course and section columns in the same form NJ carries, sourced from
Focus through the shared course-enrollment model.

**Architecture:** PR A adds `SIS`, `Standard_Course_Name` and `Core_Subject`
columns (plus Focus rows) to the course-subject crosswalk sheet, fills the
Focus-null columns of `int_students__course_enrollments`, and adds a
`rn_core_subject_year` pick column there. PR B, stacked on PR A, points the
dashboard's 3 union branches at that column and makes the self-contained filter
null-safe.

**Tech Stack:** dbt (BigQuery), Google Sheets external source, Python (throwaway
generator via `uv run --with`), BigQuery client via ADC.

**Spec:**
`docs/superpowers/specs/2026-09-24-dibels-miami-focus-schedules-design.md` — the
"Revision 2026-09-25" section governs wherever it conflicts with the original
sections below it.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-dibels-miami-focus-schedules`
  (PR A, PR #5519). Every git call is `git -C <worktree>`; every path is under
  the worktree. Never edit `/workspaces/teamster/src/...`.
- Always `uv run`; never bare `dbt` or `python`. Invoke the `dbt-local-dev`
  skill before the first dbt command of a task.
- dbt builds:
  `uv run dbt build --project-dir <worktree>/src/dbt/kipptaf --favor-state --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --select <models>`
  (absolute state path).
- `--target staging` writes (`stage_external_sources`, `dbt build`) are shared
  writes: the owner authorizes each one in the turn before it runs. Subagents
  never run them.
- No PII values in commits, PR text or comments. Query output with student rows
  stays in the terminal or the session scratchpad.
- Sheet values are exactly `PowerSchool` / `Focus` for `SIS` and `ELA` / `Math`
  / blank for `Core_Subject`. The data team maintains the sheet.
- Miami `teacherid` is the Focus staff id (`int_focus__schedule.teacher_id`,
  INT64).
- No course grade anywhere. Do not parse grades from course names in new code.
- NJ output must not change except: the 6 cross-grade duplicate student-years,
  the Paterson AY2023 `ENG01033G1` / `MAT02035G1` students, and students whose
  old row-number-1 row was a dropped section. Every other NJ difference is a
  bug.
- SQL: `.claude/rules/dbt-sql.md` — no `qualify`, no `group by all`, ST06 column
  order, rationale in properties yml rather than inline comments on this hub
  model (the model is upstream of ~184 models).
- OPEN, confirm with the owner before Task 3: the hub's final
  `full union all corresponding` stays. The SQL rules ban it and say to convert
  on edit, but converting means enumerating ~245 star-derived columns in both
  branches; this plan treats that as a separate change.

## Review Focus

1. A sheet key typed `Focus ` or `focus` makes the join miss silently, so the
   student reads unscheduled — pinned by `accepted_values` + `not_null` on `SIS`
   (Task 2).
2. An open-ended named range lands the sheet's empty grid rows as null keys —
   pinned by the staging `where` filter, `not_null` on the key, and the expected
   row count (Task 2).
3. A future-term section outranks the current one of the same subject — pinned
   by the "started term wins" verification query (Task 3).
4. A dropped section ranks 1 — pinned by the "no dropped rank-1 rows" query
   (Task 3).
5. Focus rows newly passing a consumer's filters where the consumer assumes
   PowerSchool shapes (CSGF high-school enrollment, course-name `like` filters)
   — pinned by the per-consumer audit (Task 5).

---

## PR A — sheet and shared model

### Task 0: Credentials and workspace (controller + owner; not dispatched)

**Files:** none.

- [ ] **Step 1: Owner refreshes ADC.** In VS Code, run the task **GCloud:
      Application Default Login**. It impersonates
      `codespaces@teamster-332318.iam.gserviceaccount.com` with Drive scope; the
      plain user login this session had cannot read Sheets
      (`ACCESS_TOKEN_SCOPE_INSUFFICIENT`) or Sheets-backed externals.

- [ ] **Step 2: Verify ADC type.**

  ```bash
  uv run --with google-auth python -c "import google.auth; c,_=google.auth.default(); print(type(c).__name__)"
  ```

  Expected: `Credentials` from `google.auth.impersonated_credentials` (printed
  as `Credentials`) and no "end user credentials" warning.

- [ ] **Step 3: Confirm the service account can read the crosswalk spreadsheet**
      `1G2z9rwXsFaMdFL6iOYdfQTVjZ7bctXMyz_Q09IhP4QE` (Task 1 Step 2 is the
      probe). On a 403, the owner shares it with
      `codespaces@teamster-332318.iam.gserviceaccount.com` as Viewer.

- [ ] **Step 4: Install dbt packages in the worktree.**

  ```bash
  uv run dbt deps --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-dibels-miami-focus-schedules/src/dbt/kipptaf 2>&1 | tail -n 5
  ```

### Task 1: Generate the new crosswalk tab and paste it (controller + owner)

The generator is throwaway: it lives in the session scratchpad and is never
committed. It modifies existing rows (3 new columns on every row), so the
handover is the whole tab, pasted over A1 — never a partial patch.

**Files:**

- Create (scratchpad, not committed): `<scratchpad>/build_crosswalk_v3.py`
- Output (scratchpad): `<scratchpad>/crosswalk_v3.tsv`

**Interfaces:**

- Produces: tab columns in physical order A-J = `PowerSchool_Course_Number`,
  `PowerSchool_Course_Name`, `Illuminate_Subject_Area`, `Is_Foundations`,
  `Is_Advanced_Math`, `Discipline`, `Duplicate_Audit`, `SIS`,
  `Standard_Course_Name`, `Core_Subject`; named range
  `src_assessments__course_subject_crosswalk_v3` over `A:J`.

- [ ] **Step 1: Write the generator.**

  ```python
  import csv

  import google.auth
  from google.cloud import bigquery
  from googleapiclient.discovery import build

  spreadsheet_id = "1G2z9rwXsFaMdFL6iOYdfQTVjZ7bctXMyz_Q09IhP4QE"
  v2_range = "src_assessments__course_subject_crosswalk_v2"
  out_path = "crosswalk_v3.tsv"  # run from the scratchpad directory

  # The tab's headers use spaces; dbt declares underscore names positionally,
  # so header text never reaches the warehouse. Verified 2026-09-25.
  existing_header = [
      "PowerSchool Course Number",
      "PowerSchool Course Name",
      "Illuminate Subject Area",
      "Is Foundations",
      "Is Advanced Math",
      "Discipline",
      "Duplicate Audit",
  ]
  new_header = existing_header + ["SIS", "Standard Course Name", "Core Subject"]

  # PowerSchool main-class course numbers, measured 2026-09-25 from
  # int_students__course_enrollments (AY2023-AY2026).
  ps_core = {
      "ENG01028G1": "ELA", "ENG01029G2": "ELA", "ENG01030G3": "ELA",
      "ENG01031G4": "ELA", "ENG01032G5": "ELA", "ENG01033G1": "ELA",
      "ENG01034G2": "ELA", "ENG01035G3": "ELA", "ENG01036G4": "ELA",
      "MAT02030G1": "Math", "MAT02031G2": "Math", "MAT02032G3": "Math",
      "MAT02033G4": "Math", "MAT02034G5": "Math", "MAT02035G1": "Math",
      "MAT02036G2": "Math", "MAT02037G3": "Math", "MAT02038G4": "Math",
      "MAT52069G1": "Math", "MAT02052G1": "Math", "MAT02052D1": "Math",
      "MAT02052H4": "Math",
  }

  # Focus (Florida state) course codes -> (label, subject), from the spec table.
  focus_codes = {
      "5010041": ("ELA GrK", "ELA"), "5010042": ("ELA Gr1", "ELA"),
      "5010043": ("ELA Gr2", "ELA"), "5010044": ("ELA Gr3", "ELA"),
      "5010045": ("ELA Gr4", "ELA"), "5010046": ("ELA Gr5", "ELA"),
      "1001010": ("ELA Gr6", "ELA"), "1001020": ("ELA Gr6", "ELA"),
      "1002000": ("ELA Gr6", "ELA"), "7810011": ("ELA Gr6", "ELA"),
      "1001040": ("ELA Gr7", "ELA"), "1001050": ("ELA Gr7", "ELA"),
      "1002010": ("ELA Gr7", "ELA"), "7810012": ("ELA Gr7", "ELA"),
      "1001070": ("ELA Gr8", "ELA"), "1001080": ("ELA Gr8", "ELA"),
      "1002020": ("ELA Gr8", "ELA"), "7810013": ("ELA Gr8", "ELA"),
      "5012020": ("Math GrK", "Math"), "5012030": ("Math Gr1", "Math"),
      "5012040": ("Math Gr2", "Math"), "5012050": ("Math Gr3", "Math"),
      "5012060": ("Math Gr4", "Math"), "5012070": ("Math Gr5", "Math"),
      "1205010": ("Math Gr6", "Math"), "7812015": ("Math Gr6", "Math"),
      "1205040": ("Math Gr7", "Math"), "7812020": ("Math Gr7", "Math"),
      "1205070": ("Math Gr8", "Math"), "7812030": ("Math Gr8", "Math"),
      "1200310": ("Algebra I", "Math"), "1200320": ("Algebra I", "Math"),
  }

  creds, _ = google.auth.default(
      scopes=[
          "https://www.googleapis.com/auth/spreadsheets.readonly",
          "https://www.googleapis.com/auth/drive.readonly",
      ]
  )
  svc = build("sheets", "v4", credentials=creds)

  # FORMULA render keeps Duplicate_Audit's formula text instead of its value.
  rows = (
      svc.spreadsheets()
      .values()
      .get(
          spreadsheetId=spreadsheet_id,
          range=v2_range,
          valueRenderOption="FORMULA",
      )
      .execute()
      .get("values", [])
  )
  header, body = rows[0], [r for r in rows[1:] if r and str(r[0]).strip()]
  assert header == existing_header, header
  numbers = [str(r[0]).strip() for r in body]
  assert len(numbers) == len(set(numbers)), "duplicate course numbers in v2"
  missing = sorted(set(ps_core) - set(numbers))
  assert not missing, f"PowerSchool core numbers absent from the sheet: {missing}"
  collisions = sorted(set(focus_codes) & set(numbers))
  assert not collisions, f"Focus codes collide with PowerSchool rows: {collisions}"
  print("original Duplicate_Audit, row 2:", body[0][6] if len(body[0]) > 6 else None)

  bq = bigquery.Client(project="teamster-332318")
  titles = {
      r.short_name: r.title
      for r in bq.query(
          """
          select short_name, any_value(trim(title)) as title,
          from `teamster-332318`.kipptaf_focus.int_focus__courses
          where short_name in unnest(@codes)
          group by short_name
          """,
          job_config=bigquery.QueryJobConfig(
              query_parameters=[
                  bigquery.ArrayQueryParameter("codes", "STRING", list(focus_codes))
              ]
          ),
      ).result()
  }


  def cell(value):
      if isinstance(value, bool):
          return "TRUE" if value else "FALSE"
      return "" if value is None else str(value)


  def audit(row_number):
      return f"=COUNTIFS($A:$A,$A{row_number},$H:$H,$H{row_number})"


  out = [new_header]
  for r in body:
      r = [cell(v) for v in r] + [""] * (7 - len(r))
      r = r[:7]
      row_number = len(out) + 1
      r[6] = audit(row_number)
      out.append(r + ["PowerSchool", r[1], ps_core.get(r[0].strip(), "")])

  for code, (label, subject) in focus_codes.items():
      row_number = len(out) + 1
      out.append(
          [code, titles.get(code, label), "", "", "", "", audit(row_number),
           "Focus", label, subject]
      )

  with open(out_path, "w", newline="") as f:
      csv.writer(f, delimiter="\t", lineterminator="\n").writerows(out)

  print("existing rows:", len(body), "| focus rows:", len(focus_codes),
        "| total incl header:", len(out))
  print("core ELA/Math on PowerSchool rows:",
        sum(1 for r in out[1:] if r[7] == "PowerSchool" and r[9]))
  print("focus codes without a Focus title (label used):",
        sorted(set(focus_codes) - set(titles)))
  ```

- [ ] **Step 2: Run it.**

  ```bash
  cd <scratchpad> && uv run --with google-api-python-client --with google-auth --with google-cloud-bigquery python build_crosswalk_v3.py 2>&1 | grep -v -i warn
  ```

  Expected: `existing rows: 393 | focus rows: 32 | total incl header: 426`,
  `core ELA/Math on PowerSchool rows: 22`, and the list of Focus codes with no
  title (at least `1200320`, which no Miami student takes yet). A 403 means Task
  0 Step 3.

- [ ] **Step 3: Owner pastes and names the range.** The owner opens the tab,
      selects A1, pastes `crosswalk_v3.tsv` over the whole tab, and confirms 426
      rows and 10 columns. Pasted `=COUNTIFS` text becomes formulas. Then the
      owner adds the named range `src_assessments__course_subject_crosswalk_v3`
      = `'PowerSchool Course/Subject Crosswalk'!A:J` (column-bounded,
      row-unbounded; the tab grid is 7 columns wide today, and the paste widens
      it) and leaves `_v2` in place: prod reads `_v2` until PR A merges.

### Task 2: Source, staging model and staging tests

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml` (the
  `src_google_sheets__assessments__course_subject_crosswalk` block, ~line 1281)
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__assessments__course_subject_crosswalk.sql`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__assessments__course_subject_crosswalk.yml`

**Interfaces:**

- Consumes: the v3 named range from Task 1.
- Produces: `stg_google_sheets__assessments__course_subject_crosswalk` with
  columns `SIS`, `Standard_Course_Name`, `Core_Subject` added; unique on (`SIS`,
  `PowerSchool_Course_Number`).

- [ ] **Step 1: Edit the source block only.** Bound the edit to this source's
      block (per the DIBELS skill: never a forward-scanning regex). Change
      `sheet_range: src_assessments__course_subject_crosswalk_v2` to `..._v3`,
      and append after the `Duplicate_Audit` column entry:

  ```yaml
  - name: SIS
    data_type: string
  - name: Standard_Course_Name
    data_type: string
  - name: Core_Subject
    data_type: string
  ```

  Audit the removals:
  `git -C <worktree> diff src/dbt/kipptaf/models/google/sheets/sources-external.yml | grep '^-' | grep -v '^---'`
  must show only the old `sheet_range` line.

- [ ] **Step 2: Filter phantom rows in the staging SQL.**

  ```sql
  select *,
  from
      {{
          source(
              "google_sheets",
              "src_google_sheets__assessments__course_subject_crosswalk",
          )
      }}
  where powerschool_course_number is not null
  ```

- [ ] **Step 3: Rewrite the staging properties.** Model description plus every
      column described; tested columns first. Mirror the `accepted_values`
      argument form already used elsewhere in `src/dbt/kipptaf` (grep one
      example first).

  ```yaml
  models:
    - name: stg_google_sheets__assessments__course_subject_crosswalk
      description: >-
        One row per course per SIS. Classifies PowerSchool and Focus courses for
        subject reporting and names each course's SIS-independent display label.
        Maintained by the data team.
      data_tests:
        - dbt_utils.unique_combination_of_columns:
            arguments:
              combination_of_columns:
                - SIS
                - PowerSchool_Course_Number
            config:
              severity: error
      columns:
        - name: SIS
          description: >-
            The student information system the course number belongs to,
            PowerSchool or Focus. Part of the key, because a course number is
            only unique within one SIS.
          data_type: string
          data_tests:
            - not_null:
                config:
                  severity: error
            - accepted_values:
                arguments:
                  values: [PowerSchool, Focus]
                config:
                  severity: error
        - name: PowerSchool_Course_Number
          description: >-
            The course number in its SIS. Holds the Florida state course code on
            Focus rows; the header keeps its original name because renaming a
            Sheets header rebuilds the external table.
          data_type: string
          data_tests:
            - not_null:
                config:
                  severity: error
        - name: Core_Subject
          description: >-
            ELA or Math when the course is a student's main class in that
            subject. Blank for intervention and second courses such as Intensive
            Reading, Foundational ELA and Foundation Skills Math.
          data_type: string
          data_tests:
            - accepted_values:
                arguments:
                  values: [ELA, Math]
                config:
                  severity: error
        - name: Standard_Course_Name
          description: >-
            SIS-independent display name. PowerSchool rows carry their
            PowerSchool course name; Focus rows carry the matching NJ-style
            label, for example ELA Gr3.
          data_type: string
          data_tests:
            - not_null:
                config:
                  severity: error
        - name: PowerSchool_Course_Name
          description: >-
            The course name in its SIS at the time the row was entered.
          data_type: string
        - name: Illuminate_Subject_Area
          description: >-
            Illuminate subject area used by assessment reporting. Blank on Focus
            rows.
          data_type: string
        - name: Is_Foundations
          description:
            Whether the course is a foundations course. Blank on Focus rows.
          data_type: boolean
        - name: Is_Advanced_Math
          description:
            Whether the course is an advanced math course. Blank on Focus rows.
          data_type: boolean
        - name: Discipline
          description: >-
            Academic discipline used by course and grade reporting. Blank on
            Focus rows.
          data_type: string
        - name: Duplicate_Audit
          description: >-
            Sheet formula counting rows that share this row's SIS and course
            number; above 1 marks a duplicate entry.
          data_type: int64
  ```

- [ ] **Step 4: Run the build and watch it fail first.**

  ```bash
  uv run dbt build --project-dir <worktree>/src/dbt/kipptaf --favor-state --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --select stg_google_sheets__assessments__course_subject_crosswalk > <scratchpad>/t2-build-1.log 2>&1; grep -oE "PASS=[0-9]+|ERROR=[0-9]+|WARN=[0-9]+" <scratchpad>/t2-build-1.log
  ```

  Expected: ERROR — the dev external still has the 7-column v2 shape, so the
  contract misses `SIS`.

- [ ] **Step 5: Re-stage the dev external.**

  ```bash
  uv run dbt run-operation stage_external_sources --project-dir <worktree>/src/dbt/kipptaf --target dev --args "select: google_sheets.src_google_sheets__assessments__course_subject_crosswalk" --vars '{ext_full_refresh: true}' > <scratchpad>/t2-stage.log 2>&1; tail -n 5 <scratchpad>/t2-stage.log
  ```

- [ ] **Step 6: Build again; expect all pass.** Re-run Step 4's command.
      Expected: `ERROR=0`, `WARN=0`, and the five new tests plus the model PASS.

- [ ] **Step 7: Verify the rows.** Resolve the dev relation from
      `<worktree>/src/dbt/kipptaf/target/manifest.json`
      (`.nodes["model.kipptaf.stg_google_sheets__assessments__course_subject_crosswalk"].relation_name`),
      then:

  ```sql
  select sis, core_subject, count(*) as n_rows,
  from <dev relation>
  group by sis, core_subject
  ```

  Expected: PowerSchool null 371, PowerSchool ELA 9, PowerSchool Math 13, Focus
  ELA 18, Focus Math 14 — 425 rows.

- [ ] **Step 8: Lint and commit.**

  ```bash
  cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/google/sheets/sources-external.yml src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__assessments__course_subject_crosswalk.sql src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__assessments__course_subject_crosswalk.yml </dev/null 2>&1 | tail -n 5
  git -C <worktree> add -u && git -C <worktree> commit -m "feat(dbt): key the course-subject crosswalk on SIS and add Focus rows" -m "Refs #5518" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

### Task 3: Fill Focus columns and add `rn_core_subject_year` in the shared model

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__course_enrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__course_enrollments.yml`
- Create:
  `src/dbt/kipptaf/tests/int_students__course_enrollments__core_sections_cover_k8.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml`

**Interfaces:**

- Consumes: Task 2's staging columns `sis`, `standard_course_name`,
  `core_subject` (BigQuery resolves the PascalCase headers case-insensitively).
- Produces on `int_students__course_enrollments`: `standard_course_name` STRING,
  `core_subject` STRING (`ELA`/`Math`/null), `rn_core_subject_year` INT64 (1 =
  the student's primary section in `core_subject` at that school that year; null
  on non-core or dropped rows). Focus rows now carry `courses_course_name`,
  `cc_section_number`, `cc_teacherid`, `teacher_lastfirst`,
  `rn_course_number_year`.

- [ ] **Step 1: Write the failing coverage test.**

  ```sql
  -- tests/int_students__course_enrollments__core_sections_cover_k8.sql
  with
      -- grain projection, not dup-masking: one row per student per school-year,
      -- collapsing multiple enrollment stints at the same school
      k8_students as (
          select distinct
              academic_year, _dbt_source_project, region, schoolid, student_number,
          from {{ ref("int_extracts__student_enrollments") }}
          where
              academic_year = {{ var("current_academic_year") }}
              and grade_level between 0 and 8
      ),

      expected as (
          select
              s.academic_year,
              s._dbt_source_project,
              s.region,
              s.schoolid,
              s.student_number,

              subject,
          from k8_students as s
          cross join unnest(['ELA', 'Math']) as subject
      ),

      core_sections as (
          select
              cc_academic_year,
              _dbt_source_project,
              cc_schoolid,
              students_student_number,
              core_subject,
          from {{ ref("int_students__course_enrollments") }}
          where rn_core_subject_year = 1
      ),

      coverage as (
          select
              e.region,
              e.subject,

              count(*) as n_students,
              countif(c.students_student_number is not null) as n_with_core_section,
              safe_divide(
                  countif(c.students_student_number is not null), count(*)
              ) as coverage_rate,
          from expected as e
          left join
              core_sections as c
              on e.academic_year = c.cc_academic_year
              and e._dbt_source_project = c._dbt_source_project
              and e.schoolid = c.cc_schoolid
              and e.student_number = c.students_student_number
              and e.subject = c.core_subject
          group by e.region, e.subject
      )

  select region, subject, n_students, n_with_core_section, coverage_rate,
  from coverage
  where coverage_rate < 0.95
  ```

  Add to `tests/properties.yml`, mirroring the neighboring
  `test_focus_course_enrollment_joins_resolve_miami` entry's shape
  (`config.meta.dagster.ref.name: int_students__course_enrollments`):

  ```yaml
  - name: int_students__course_enrollments__core_sections_cover_k8
    description: >-
      Warns when fewer than 95% of a region's K-8 students this academic year
      hold a primary ELA or math section (`rn_core_subject_year = 1`). The
      likeliest cause is a course missing from the course-subject crosswalk
      sheet -- a new Florida code or a renumbered PowerSchool course -- which
      otherwise leaves students unscheduled with no error. Measured 2026-09-25
      before this test existed: 97.4% NJ and 98.6% Miami for math.
  ```

  Run it:

  ```bash
  uv run dbt build --project-dir <worktree>/src/dbt/kipptaf --favor-state --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --select int_students__course_enrollments__core_sections_cover_k8 > <scratchpad>/t3-test-1.log 2>&1; grep -oE "PASS=[0-9]+|ERROR=[0-9]+|WARN=[0-9]+" <scratchpad>/t3-test-1.log
  ```

  Expected: ERROR — `rn_core_subject_year` does not exist yet.

- [ ] **Step 2: PowerSchool branch — SIS match and 2 sheet columns.** In
      `powerschool_conformed`, after `csc.discipline,` add:

  ```sql
              csc.standard_course_name,
              csc.core_subject,
  ```

  and change its crosswalk join to:

  ```sql
          left join
              {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }} as csc
              on a.cc_course_number = csc.powerschool_course_number
              and csc.sis = 'PowerSchool'
  ```

- [ ] **Step 3: Focus branch — fill the columns.** In `focus_conformed`:
  - after `s.end_date as cc_dateleft,` add
    `s.course_period_short_name as cc_section_number,` and
    `s.teacher_id as cc_teacherid,`
  - after `s._dbt_source_project,` add a blank line then
    `csc.standard_course_name,` and `csc.core_subject,`
  - after `{{ extract_region("s") }} as region,` add
    `trim(s.course_title) as courses_course_name,` and
    `concat(usr.last_name, ', ', usr.first_name) as teacher_lastfirst,`
  - after the `sr_email` join, add:

  ```sql
          left join
              {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }} as csc
              on c.short_name = csc.powerschool_course_number
              and csc.sis = 'Focus'
  ```

  Before committing, confirm the PowerSchool `teacher_lastfirst` format is
  `Last, First` (count rows matching `r'^[^,]+, [^,]+$'` on NJ AY2026); if it
  differs, match it.

- [ ] **Step 4: Focus `rn_course_number_year`.** In `focus_course_dropped`,
      after the `is_dropped_course` window, add:

  ```sql
              row_number() over (
                  partition by
                      _dbt_source_project,
                      students_student_number,
                      cc_academic_year,
                      cc_course_number
                  order by cc_dateenrolled desc, exit_date desc
              ) as rn_course_number_year,
  ```

- [ ] **Step 5: Add the pick column after the union.** Replace the final 5 lines
      (`select *, from powerschool_conformed ... from focus_course_dropped`)
      with 2 more CTEs and a final select:

  ```sql
      unioned as (
          select *,
          from powerschool_conformed

          full union all corresponding

          select *,
          from focus_course_dropped
      ),

      core_section_inputs as (
          select
              *,

              core_subject is not null
              and not is_dropped_section as is_core_section_candidate,

              cc_dateenrolled
              <= current_date('{{ var("local_timezone") }}') as is_term_started,

              countif(not is_dropped_section) over (
                  partition by _dbt_source_project, cc_academic_year, cc_sectionid
              ) as section_enrolled_count,
          from unioned
      )

  select
      * except (is_core_section_candidate, is_term_started, section_enrolled_count),

      if(
          is_core_section_candidate,
          row_number() over (
              partition by
                  _dbt_source_project,
                  cc_academic_year,
                  cc_schoolid,
                  students_student_number,
                  core_subject,
                  is_core_section_candidate
              order by
                  is_term_started desc,
                  cc_dateenrolled desc,
                  section_enrolled_count desc,
                  cc_section_number asc,
                  cc_dcid asc
          ),
          null
      ) as rn_core_subject_year,
  from core_section_inputs
  ```

  No inline rationale comments: the "why" goes in the yml (Step 6).

- [ ] **Step 6: Properties.** Add column entries (descriptions only; the model
      is not contract-enforced — confirm no `contract:` in its config):
  - `standard_course_name` — SIS-independent course label from the crosswalk
    sheet, matched on SIS and course number.
  - `core_subject` — ELA or Math when the course is the student's main class in
    that subject, from the crosswalk sheet; null otherwise.
  - `rn_core_subject_year` — 1 marks the student's primary section in
    `core_subject` at that school that year. Ranks only rows with a
    `core_subject` that are not `is_dropped_section`, and is null on every other
    row. Order: term already started first (Focus dates a section to its marking
    period, so a future-term row carries a future date), then latest
    `cc_dateenrolled`, then the larger roster of non-dropped students (a same-
    teacher small-group section loses to the full class), then
    `cc_section_number`, then `cc_dcid`. School is in the partition so a
    mid-year transfer keeps a section per school. No course grade is used: no
    SIS course grade is populated reliably.
  - `courses_course_name`, `cc_section_number`, `cc_teacherid`,
    `teacher_lastfirst`, `rn_course_number_year` — add entries that say what
    each holds on PowerSchool rows and on Focus rows (trimmed Focus course
    title; course period short name; Focus staff id, a different id space from
    PowerSchool's; `Last, First` from `int_focus__users`; PowerSchool's
    definition without `cc_termid`, ordered by `cc_dateenrolled` then
    `exit_date`).
  - Update the model description to say the Focus branch now carries course
    name, section, teacher and course row number.

- [ ] **Step 7: Build the model and the test.**

  ```bash
  uv run dbt build --project-dir <worktree>/src/dbt/kipptaf --favor-state --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --select stg_google_sheets__assessments__course_subject_crosswalk int_students__course_enrollments int_students__course_enrollments__core_sections_cover_k8 > <scratchpad>/t3-build.log 2>&1; grep -oE "PASS=[0-9]+|ERROR=[0-9]+|WARN=[0-9]+" <scratchpad>/t3-build.log
  ```

  Expected: `ERROR=0`; the coverage test PASS (not WARN).

- [ ] **Step 8: Verify the pick (Review Focus 3 and 4).** Against the dev
      relation of `int_students__course_enrollments`, each must return 0:

  ```sql
  -- a dropped or non-core row ranked
  select count(*),
  from <dev>
  where rn_core_subject_year is not null
      and (is_dropped_section or core_subject is null)
  ```

  ```sql
  -- a not-yet-started section ranked 1 while a started candidate exists
  with
      cands as (
          select
              _dbt_source_project, cc_academic_year, cc_schoolid,
              students_student_number, core_subject, rn_core_subject_year,
              cc_dateenrolled <= current_date('America/New_York') as is_started,
          from <dev>
          where rn_core_subject_year is not null
      ),

      groups_ as (
          select
              _dbt_source_project, cc_academic_year, cc_schoolid,
              students_student_number, core_subject,
              logical_or(is_started) as any_started,
              logical_or(rn_core_subject_year = 1 and is_started) as first_started,
          from cands
          group by
              _dbt_source_project, cc_academic_year, cc_schoolid,
              students_student_number, core_subject
      )

  select count(*),
  from groups_
  where any_started and not first_started
  ```

  And the unchanged-rows check. Write `<scratchpad>/diff_hub.py`:

  ```python
  import sys

  from google.cloud import bigquery

  client = bigquery.Client(project="teamster-332318")
  prod = "`teamster-332318`.kipptaf_students.int_students__course_enrollments"
  dev = sys.argv[1]  # the dev relation_name from manifest.json, backticked
  filled = {
      "courses_course_name",
      "cc_section_number",
      "cc_teacherid",
      "teacher_lastfirst",
      "rn_course_number_year",
  }

  cols = [
      r.column_name
      for r in client.query(
          """
          select column_name,
          from `teamster-332318`.kipptaf_students.INFORMATION_SCHEMA.COLUMNS
          where table_name = 'int_students__course_enrollments'
          order by ordinal_position
          """
      ).result()
  ]

  # Focus coverage starts at AY2026 today (min academic_year in int_focus__schedule).
  focus = "(_dbt_source_project = 'kippmiami' and cc_academic_year >= 2026)"


  def compare(label, where, columns):
      row = ", ".join(f"`{c}`" for c in columns)
      for a, b, side in ((prod, dev, "prod"), (dev, prod, "dev")):
          sql = f"""
          select count(*) as n,
          from (
              select to_json_string(struct({row})) as j, from {a} where {where}
              except distinct
              select to_json_string(struct({row})) as j, from {b} where {where}
          )
          """
          n = next(iter(client.query(sql).result())).n
          print(f"{label}: rows only in {side} = {n}")
      for rel, side in ((prod, "prod"), (dev, "dev")):
          sql = f"select count(*) as n, from {rel} where {where}"
          print(f"{label}: {side} row count = {next(iter(client.query(sql).result())).n}")


  compare("unchanged set", f"not {focus}", cols)
  compare("focus set, filled columns excluded", focus, [c for c in cols if c not in filled])
  ```

  Run
  `uv run --with google-cloud-bigquery python <scratchpad>/diff_hub.py '<dev relation>'`.
  Expected: every "rows only in" line is 0, and prod and dev row counts match
  for both sets.

- [ ] **Step 9: Lint and commit.**

  ```bash
  cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/students/intermediate/int_students__course_enrollments.sql src/dbt/kipptaf/models/students/intermediate/properties/int_students__course_enrollments.yml src/dbt/kipptaf/tests/int_students__course_enrollments__core_sections_cover_k8.sql src/dbt/kipptaf/tests/properties.yml </dev/null 2>&1 | tail -n 5
  git -C <worktree> add src/dbt/kipptaf/tests/int_students__course_enrollments__core_sections_cover_k8.sql && git -C <worktree> add -u && git -C <worktree> commit -m "feat(dbt): conform Focus sections and pick a primary core section per student" -m "Refs #5518" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```

### Task 4: `dim_courses` SIS match

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_courses.sql`

- [ ] **Step 1: Add the SIS match.**

  ```sql
  left join
      {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }} as csc
      on c.course_number = csc.powerschool_course_number
      and csc.sis = 'PowerSchool'
  ```

  `int_students__courses` unions PowerSchool and Focus courses with no SIS
  column; Focus courses never matched the sheet before, and their new sheet rows
  carry blank `Discipline` and `Is_Foundations`, so restricting to PowerSchool
  keeps every output value as it is.

- [ ] **Step 2: Build and prove no change.**

  ```bash
  uv run dbt build --project-dir <worktree>/src/dbt/kipptaf --favor-state --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --select dim_courses > <scratchpad>/t4-build.log 2>&1; grep -oE "PASS=[0-9]+|ERROR=[0-9]+|WARN=[0-9]+" <scratchpad>/t4-build.log
  ```

  Then `to_json_string(t)` `except distinct` between prod
  `kipptaf_marts.dim_courses` and the dev relation, both directions. Expected: 0
  and 0.

- [ ] **Step 3: Commit.**
      `feat(dbt): match dim_courses to the crosswalk's PowerSchool rows`.

### Task 5: Consumer audit (dispatch to the capable model)

**Files:**

- Create (scratchpad): `<scratchpad>/consumer-audit.md`
- Modify: only if the owner approves a scoping change in Step 3.

- [ ] **Step 1: List consumers.** Every model that refs
      `int_students__course_enrollments` or
      `base_powerschool__course_enrollments` and reads `courses_course_name`,
      `cc_section_number`, `cc_teacherid`, `teacher_lastfirst`,
      `rn_course_number_year` or `rn_credittype_year` (34 found on 2026-09-25;
      20 filter on a row number).

- [ ] **Step 2: Classify each** by reading its SQL: (a) Focus rows still
      excluded by another predicate (PowerSchool-only course names, credit type,
      explicit region filter); (b) Focus rows newly admitted. For every (b), run
      its hub-side predicate set against the dev hub and count Miami AY2026 rows
      that now pass. Known must-reads: `rpt_gsheets__csgf_hs_enrollment` (feeds
      the external CSGF submission; its `%Honors%` / `%(DE)` flags are
      case-sensitive and Focus titles are uppercase), `rpt_tableau__crdc_roster`
      (`%(DE)`), `int_extracts__student_enrollments` (the spine), and the 3
      Miami dashboards (refreshes off per the owner; list, no action).

- [ ] **Step 3: Report and decide.** Write `consumer-audit.md`: one row per
      consumer, class, Miami rows gained, NJ rows changed (must be 0). Hand
      every (b) consumer to the owner for accept or scope-out before PR A leaves
      draft.

### Task 6: Stage for CI, push, and ready PR A (controller + owner)

- [ ] **Step 1: Owner authorizes the staging re-stage**, then run in its own
      Bash call:

  ```bash
  uv run dbt run-operation stage_external_sources --project-dir <worktree>/src/dbt/kipptaf --target staging --args "select: google_sheets.src_google_sheets__assessments__course_subject_crosswalk" --vars '{ext_full_refresh: true}'
  ```

- [ ] **Step 2: Push and update PR #5519.** Retitle to
      `feat(dbt): conform Focus course sections in int_students__course_enrollments`;
      rewrite the body from `.github/pull_request_template.md` (plain language;
      `Refs #5518`); include the consumer audit summary and the
      `full union all corresponding` decision. Invoke `pr-ci-review` before
      marking ready. CI's `state:modified+` covers the hub's whole descendant
      graph — budget for unrelated latent failures and check each against prod
      before treating it as caused here.

---

## PR B — DIBELS dashboard (stacked on PR A)

### Task 7: Stacked branch (controller + owner)

- [ ] **Step 1: Confirm worktree with the owner**, then:

  ```bash
  cd /workspaces/teamster && gh issue develop 5518 --name anthonygwalters/feat/claude-dibels-miami-dashboard-schedules --base anthonygwalters/feat/claude-dibels-miami-focus-schedules
  git fetch origin anthonygwalters/feat/claude-dibels-miami-dashboard-schedules
  git worktree add /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-dibels-miami-dashboard-schedules anthonygwalters/feat/claude-dibels-miami-dashboard-schedules
  git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-dibels-miami-dashboard-schedules branch --unset-upstream
  ```

  All PR B paths below are under this second worktree (`<wtB>`). Run `dbt deps`
  there first.

### Task 8: Point the dashboard at the primary ELA section

**Files:**

- Modify:
  `<wtB>/src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__dibels_dashboard.sql`
- Modify: its properties yml
  (`extracts/tableau/properties/rpt_tableau__dibels_dashboard.yml`)

**Interfaces:**

- Consumes: Task 3's `core_subject`, `rn_core_subject_year`,
  `standard_course_name`.
- Produces: no column change. Output names stay `schedule_student_number`,
  `teacherid`, `teacher_name`, `course_name`, `course_number`, `section_number`,
  `schedule_student_grade_level`, `scheduled`.

- [ ] **Step 1: Replace the join in all 3 branches.** Each branch's
      `left join {{ ref("base_powerschool__course_enrollments") }} as c ...`
      block (through the `courses_course_name in (...)` list) becomes:

  ```sql
  left join
      {{ ref("int_students__course_enrollments") }} as c
      on s.academic_year = c.cc_academic_year
      and s.schoolid = c.cc_schoolid
      and s.student_number = c.students_student_number
      and s._dbt_source_project = c._dbt_source_project
      and c.core_subject = 'ELA'
      and c.rn_core_subject_year = 1
      and c.cc_section_number not like '%SC%'
  ```

- [ ] **Step 2: Projections, in all 3 branches.**
      `c.courses_course_name as course_name` becomes
      `c.standard_course_name as course_name`, and
      `right(c.courses_course_name, 1) as schedule_student_grade_level` becomes
      `right(c.standard_course_name, 1) as schedule_student_grade_level`. Leave
      every other `c.` column as it is.

- [ ] **Step 3: Null-safe filter, in all 3 branches.**
      `and not s.is_self_contained` becomes
      `and s.is_self_contained is not true`.

- [ ] **Step 4: Descriptions.** In the yml, rewrite the schedule columns'
      descriptions to cover both SIS: `teacherid` is the PowerSchool teacher id
      for NJ and for Miami before AY2026, and the Focus staff id for Miami from
      AY2026; `course_name` is the crosswalk sheet's standard label; drop any
      "PowerSchool-only" or "null for Miami" wording.

- [ ] **Step 5: Union-branch balance.** The DIBELS skill's
      `gr-diff-union-branches.py` is not in either checkout, so write
      `<scratchpad>/union_balance.py`:

  ```python
  import re
  import sys

  sql = re.sub(r"--[^\n]*", "", open(sys.argv[1]).read())
  branches = re.split(r"\n\s*union all\s*\n", sql)


  def aliases(branch):
      body = branch[branch.lower().index("select") + len("select") :]
      body = re.split(r"\nfrom ", body, maxsplit=1)[0]
      items, depth, cur = [], 0, ""
      for ch in body:
          depth += ch == "("
          depth -= ch == ")"
          if ch == "," and depth == 0:
              items.append(cur)
              cur = ""
          else:
              cur += ch
      items.append(cur)
      names = []
      for item in (i.strip() for i in items):
          if not item:
              continue
          m = re.search(r"\bas\s+([a-z_][a-z0-9_]*)\s*$", item, re.I | re.S)
          names.append(m.group(1) if m else item.split(".")[-1].strip())
      return names


  lists = [aliases(b) for b in branches]
  print("branches:", len(lists), "| projections:", [len(x) for x in lists])
  bad = [(i, *names) for i, names in enumerate(zip(*lists)) if len(set(names)) > 1]
  print("mismatched ordinals:", len(bad))
  for b in bad[:10]:
      print(b)
  ```

  Run it on the edited SQL. Expected: `branches: 3`, 3 equal counts,
  `mismatched ordinals: 0`. Then `grep -c "^      - name: "` on the yml equals
  that count.

- [ ] **Step 6: Build.** In `<wtB>`, build
      `stg_google_sheets__assessments__course_subject_crosswalk int_students__course_enrollments rpt_tableau__dibels_dashboard`
      with the standard flags (PR B needs PR A's models in the same dev build).
      Expected: `ERROR=0`; existing dashboard singular tests pass or warn only
      where prod already warns.

- [ ] **Step 7: Dev against prod, grouped by `model_type`.**
  - NJ: row counts and the 6 schedule columns match prod except the 3 listed
    cases (Global Constraints). List every other difference; each is a bug.
  - Miami: rows and students per `academic_year` and `model_type` against the
    spec's estimates (Benchmark AY2023 9,064 / AY2024 20,557 / AY2025 20,400 /
    AY2026 22,044); `scheduled` rate per year at least 97% for AY2023-AY2025 and
    about 98% for AY2026.
  - Report, do not fix: whether the Benchmark goal join (`s.school = g.school`)
    matches Focus-era Miami school names.

- [ ] **Step 8: Lint and commit.** trunk check the SQL and yml; commit
      `feat(dbt): show Miami on the DIBELS dashboard with Focus ELA schedules`
      with `Refs #5518`.

### Task 9: DIBELS docs and skill

**Files:**

- Modify: `<wtB>/docs/models/dibels-dashboard-data-model.md`
- Modify: `<wtB>/.claude/skills/dibels-dashboard/SKILL.md`

- [ ] **Step 1: Skill.** Replace the "PowerSchool-only: null for Miami (Focus)
      students" paragraph (Bright Spots section) with where schedules now come
      from (`int_students__course_enrollments`, `core_subject = 'ELA'`,
      `rn_core_subject_year = 1`, the crosswalk sheet). Correct the "A whole
      region missing" section: `is_self_contained` was a wrong cause for missing
      AY2026 scores but did drop every Miami row from the dashboard until this
      change. Add: ACCESS course titles abbreviate Language Arts to `LA`, so a
      title search for `LANG` misses them; and the Florida codes live on the
      crosswalk sheet, not in SQL.

- [ ] **Step 2: Reference doc.** Update the filter list (`not is_self_contained`
      → `is_self_contained is not true`, with the reason) and the
      schedule-column description to name both SIS and the sheet.

- [ ] **Step 3: Lint and commit.** trunk check both files; commit
      `docs(dbt): record Miami schedules on the DIBELS dashboard`.

### Task 10: Open PR B (controller)

- [ ] **Step 1:** Push `<wtB>`'s branch and open a draft PR with base
      `anthonygwalters/feat/claude-dibels-miami-focus-schedules`, body from the
      template, `Closes #5518`. Note in the body that a stacked PR runs only
      Trunk, so its dbt verification is the local results above; retarget to
      `main` once PR A merges, then CI runs.
