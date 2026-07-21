# College Board AP Data Ingest Protocol Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the validated College Board AP pipeline audit (ingestion
freshness, codes/course-tagging completeness, tiered crosswalk-ID matching with
corroboration, staged batch delivery, post-paste reconciliation, downstream
lineage verification) into a `.claude/skills/` skill so it can be re-run every
admin year without re-deriving the queries.

**Architecture:** A `SKILL.md` runbook (phases matching the design spec's
13-step workflow) that references four standalone `.sql` files under `queries/`
— one per check (codes completeness, AP course tagging, tiered crosswalk match,
downstream lineage). Every query was executed live against the real 2025-2026
backlog during design and is copied here verbatim from that validated run, not
re-derived. Validated by dispatching a fresh subagent with only the skill loaded
against the current (now fully resolved) pipeline state, confirming it correctly
reports a clean state rather than inventing problems, and that it never proposes
writing PII to a committed file.

**Tech Stack:** Markdown (Claude Code skill format), BigQuery SQL (GoogleSQL
dialect), Dagster MCP tools, BigQuery MCP tools.

## Global Constraints

- PII (student names, DOB, gender) never gets written to any file committed to
  git — chat/terminal only.
- No fuzzy/similarity name matching — only deterministic transforms (case-fold,
  diacritic-strip, hyphen/space token-split, exact ±1-year day-count
  comparison).
- Never write directly to the Google Sheet — no tool can do it; always produce
  copy/paste-ready output for the human.
- Always ask before launching a Dagster run (`confirm=True`) — preview first
  with `confirm=False`.
- Batches of 20 delivered one at a time with explicit confirmation between each
  — never dump all batches at once.
- Gender mismatch on a Tier C/D match is a hard gate — moves the row out of
  `resolved` into `flagged_for_review`.
- Course-enrollment check is informational only for Tier C/D — never used to
  include/exclude a match.
- `base_powerschool__course_enrollments` join for course corroboration uses
  `ap_course_subject` (not `cc_course_number`), filtered to
  `rn_course_number_year = 1` and `not is_dropped_section`, bridged across
  district-union tables via
  `regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` matching on both sides.
- Codes completeness check scopes to rows with a non-null `exam_grade` only —
  unscored placeholder slots produce false positives otherwise.
- AP course tagging check flags unconditionally (regardless of whether the gap
  happens to affect this cycle's matching), scoped to `academic_year >= 2024`.
- Full spec:
  `docs/superpowers/specs/2026-07-13-collegeboard-ap-pipeline-audit-design.md`.

## File Structure

```text
.claude/skills/collegeboard-ap-data-ingest-protocol/
  SKILL.md                          # runbook: 13-phase workflow
  queries/
    01-codes-completeness.sql       # Codes Completeness Check
    02-ap-course-tagging.sql        # AP Course Tagging Check
    03-tiered-crosswalk-match.sql   # Tiers A-D + tiebreak + corroboration
    04-downstream-lineage.sql       # int_collegeboard__ap_unpivot + dashboard
```

Each `.sql` file is self-contained and copy-paste-runnable via the BigQuery MCP
`execute_sql` tool as-is (no template variables to fill in), except
`04-downstream-lineage.sql`, which has one placeholder year to substitute
(commented inline) since a lineage check is inherently scoped to a specific
admin year, unlike the other three checks which self-scope automatically.

## Task 1: Codes Completeness Query

**Files:**

- Create:
  `.claude/skills/collegeboard-ap-data-ingest-protocol/queries/01-codes-completeness.sql`

**Interfaces:**

- Consumes: `kipptaf_collegeboard.stg_collegeboard__ap`,
  `kipptaf_google_sheets.stg_google_sheets__collegeboard__ap_codes`
- Produces: rows of `(expected_domain, missing_code)` — empty result means no
  gaps

- [ ] **Step 1: Write the query**

```sql
-- Codes Completeness Check
--
-- Confirms every exam/irregularity code the raw AP file actually uses on a
-- SCORED row (a record with a real exam_grade) is present in
-- stg_google_sheets__collegeboard__ap_codes. Must scope to scored rows only:
-- validated during design that exam codes "1"/"2" appear in the raw file
-- but only on unscored placeholder slots (exam_grade is null) - including
-- those produces false positives on every run.
--
-- Empty result = no gaps. A non-empty result means: identify the missing
-- code(s) below, look up the meaning by fetching (not just search-summarizing)
-- the current College Board "AP Student Datafile for Schools and Districts
-- [Year] Layout Format" PDF at apcentral.collegeboard.org, then hand the user
-- the missing code + looked-up description + the direct URL to the ap_codes
-- sheet tab so they can add the row manually (no Sheets write access here):
-- https://docs.google.com/spreadsheets/d/1dmPEB3lVBwNhcGANh1H8_D42nK3zIrFFE0rBFZQBuxE
-- tab: src_collegeboard__ap_codes

with scored_rows as (
  select exam_code, irregularity_code_1, irregularity_code_2, exam_grade
  from `teamster-332318`.kipptaf_collegeboard.stg_collegeboard__ap
  unpivot (
    (exam_code, exam_grade, irregularity_code_1, irregularity_code_2) for rn_exam_number in (
      (exam_code_01, exam_grade_01, irregularity_code_1_01, irregularity_code_2_01),
      (exam_code_02, exam_grade_02, irregularity_code_1_02, irregularity_code_2_02),
      (exam_code_03, exam_grade_03, irregularity_code_1_03, irregularity_code_2_03),
      (exam_code_04, exam_grade_04, irregularity_code_1_04, irregularity_code_2_04),
      (exam_code_05, exam_grade_05, irregularity_code_1_05, irregularity_code_2_05),
      (exam_code_06, exam_grade_06, irregularity_code_1_06, irregularity_code_2_06),
      (exam_code_07, exam_grade_07, irregularity_code_1_07, irregularity_code_2_07),
      (exam_code_08, exam_grade_08, irregularity_code_1_08, irregularity_code_2_08),
      (exam_code_09, exam_grade_09, irregularity_code_1_09, irregularity_code_2_09),
      (exam_code_10, exam_grade_10, irregularity_code_1_10, irregularity_code_2_10),
      (exam_code_11, exam_grade_11, irregularity_code_1_11, irregularity_code_2_11),
      (exam_code_12, exam_grade_12, irregularity_code_1_12, irregularity_code_2_12),
      (exam_code_13, exam_grade_13, irregularity_code_1_13, irregularity_code_2_13),
      (exam_code_14, exam_grade_14, irregularity_code_1_14, irregularity_code_2_14),
      (exam_code_15, exam_grade_15, irregularity_code_1_15, irregularity_code_2_15),
      (exam_code_16, exam_grade_16, irregularity_code_1_16, irregularity_code_2_16),
      (exam_code_17, exam_grade_17, irregularity_code_1_17, irregularity_code_2_17),
      (exam_code_18, exam_grade_18, irregularity_code_1_18, irregularity_code_2_18),
      (exam_code_19, exam_grade_19, irregularity_code_1_19, irregularity_code_2_19),
      (exam_code_20, exam_grade_20, irregularity_code_1_20, irregularity_code_2_20),
      (exam_code_21, exam_grade_21, irregularity_code_1_21, irregularity_code_2_21),
      (exam_code_22, exam_grade_22, irregularity_code_1_22, irregularity_code_2_22),
      (exam_code_23, exam_grade_23, irregularity_code_1_23, irregularity_code_2_23),
      (exam_code_24, exam_grade_24, irregularity_code_1_24, irregularity_code_2_24),
      (exam_code_25, exam_grade_25, irregularity_code_1_25, irregularity_code_2_25),
      (exam_code_26, exam_grade_26, irregularity_code_1_26, irregularity_code_2_26),
      (exam_code_27, exam_grade_27, irregularity_code_1_27, irregularity_code_2_27),
      (exam_code_28, exam_grade_28, irregularity_code_1_28, irregularity_code_2_28),
      (exam_code_29, exam_grade_29, irregularity_code_1_29, irregularity_code_2_29),
      (exam_code_30, exam_grade_30, irregularity_code_1_30, irregularity_code_2_30)
    )
  )
  where exam_grade is not null
),
file_exam_codes as (
  select distinct exam_code as code from scored_rows where exam_code is not null
),
file_irreg_codes as (
  select distinct code from (
    select irregularity_code_1 as code from scored_rows where irregularity_code_1 is not null
    union all
    select irregularity_code_2 from scored_rows where irregularity_code_2 is not null
  )
),
known_codes as (
  select code, `domain`
  from `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__collegeboard__ap_codes
)
select 'Exam Codes' as expected_domain, f.code as missing_code
from file_exam_codes f
where not exists (
  select 1 from known_codes k where k.code = f.code and k.`domain` = 'Exam Codes'
)
union all
select 'Irregularity Scores', f.code
from file_irreg_codes f
where not exists (
  select 1 from known_codes k where k.code = f.code and k.`domain` = 'Irregularity Scores'
)
```

- [ ] **Step 2: Run it via the BigQuery MCP `execute_sql` tool**

Expected: `"The query returned 0 rows."` against the current warehouse state
(validated 2025-2026: zero gaps). A non-empty result is a real finding, not a
failure of the query itself.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/collegeboard-ap-data-ingest-protocol/queries/01-codes-completeness.sql
git commit -m "feat: add codes completeness query to AP ingest protocol skill"
```

## Task 2: AP Course Tagging Query

**Files:**

- Create:
  `.claude/skills/collegeboard-ap-data-ingest-protocol/queries/02-ap-course-tagging.sql`

**Interfaces:**

- Consumes: `kipptaf_powerschool.base_powerschool__course_enrollments`
- Produces: rows of
  `(cc_academic_year, cc_course_number, courses_course_name, ap_course_subject)`
  where `ap_course_subject` is always `NULL` (that's the gap) — empty result
  means no gaps

- [ ] **Step 1: Write the query**

```sql
-- AP Course Tagging Check
--
-- ap_course_subject comes from PowerSchool's NJ state course-extension
-- table (stg_powerschool__s_nj_crs_x, joined by coursesdcid) - a course-setup
-- field a human sets directly in PowerSchool, independent of the crosswalk
-- sheet. is_ap_course is literally defined as `ap_course_subject is not
-- null`, so a course that already has the field set can't fail this check
-- by definition - the real gap is a course whose NAME signals AP but was
-- never tagged. Flag unconditionally: a course still gets flagged even if
-- its exam type happens to already resolve fine through a different,
-- correctly-tagged course elsewhere (validated case: ENG22110C4 "AP Seminar"
-- at KIPP Newark Collegiate Academy was untagged, but Seminar exam matching
-- still worked via a separate, correctly-tagged Seminar section - the
-- tagging gap on ENG22110C4 is still real and still gets flagged).
--
-- Scoped to academic_year >= 2024 per user direction (older history isn't
-- actionable). This is a PowerSchool course-setup miss with no PII involved -
-- hand the result to whoever owns PowerSchool course setup; no write access
-- to PowerSchool here.

select distinct
  cc_academic_year,
  cc_course_number,
  courses_course_name,
  ap_course_subject
from `teamster-332318`.kipptaf_powerschool.base_powerschool__course_enrollments
where cc_academic_year >= 2024
  and regexp_contains(courses_course_name, r'\bAP\b')
  and ap_course_subject is null
order by cc_academic_year, courses_course_name
```

- [ ] **Step 2: Run it via the BigQuery MCP `execute_sql` tool**

Expected (validated 2025-2026): exactly one row —
`cc_academic_year=2025, cc_course_number='ENG22110C4', courses_course_name='AP Seminar', ap_course_subject=NULL`.
If the result differs, that's real data drift, not a query problem — report
whatever the query actually returns.

To find which district/region owns a flagged course (needed to route the fix),
follow up with:

```sql
select distinct _dbt_source_relation, cc_schoolid
from `teamster-332318`.kipptaf_powerschool.base_powerschool__course_enrollments
where cc_academic_year = <flagged_year>
  and cc_course_number = '<flagged_course_number>'
```

then resolve `cc_schoolid` to a school name via
`kipptaf_powerschool.base_powerschool__student_enrollments`
(`schoolid`/`school_name` columns, same academic_year).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/collegeboard-ap-data-ingest-protocol/queries/02-ap-course-tagging.sql
git commit -m "feat: add AP course tagging query to AP ingest protocol skill"
```

## Task 3: Tiered Crosswalk Match Query

**Files:**

- Create:
  `.claude/skills/collegeboard-ap-data-ingest-protocol/queries/03-tiered-crosswalk-match.sql`

**Interfaces:**

- Consumes: `kipptaf_collegeboard.stg_collegeboard__ap`,
  `kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves`,
  `kipptaf_powerschool.base_powerschool__student_enrollments`,
  `kipptaf_google_sheets.stg_google_sheets__collegeboard__ap_codes`,
  `kipptaf_google_sheets.stg_google_sheets__collegeboard__ap_course_crosswalk`,
  `kipptaf_powerschool.base_powerschool__course_enrollments`
- Produces: rows of
  `(ap_number_ap_id, student_number, tiers, bucket, enrolled_in_matching_course)`
  — `bucket` is one of `resolved`, `flagged_for_review`, `no_match`

- [ ] **Step 1: Write the query**

```sql
-- Tiered Crosswalk Match + Tier C/D Corroboration
--
-- Self-scoping by academic_year = enrollment_school_year (each gap's own
-- year) - no manual parameter needed, works unchanged every year.
--
-- Tiers:
--   A/B - exact DOB + last_name (raw, or diacritic-stripped on both sides)
--   C   - exact DOB + shared last_name TOKEN (split on hyphen/space) -
--         handles compound/hyphenated surnames recorded inconsistently
--         between CB and PowerSchool (CB "Alvarado" vs PS "Alvarado Jr";
--         CB "Morgan-Wallace" vs PS "Morgan Wallace"; CB "Jones" vs PS
--         "Jones-Laberth")
--   D   - DOB exactly 365/366 days apart (same month/day, year off by one,
--         leap-year safe) AND both first_name and last_name match exactly -
--         handles a DOB-year transcription mismatch. Requires both names
--         (not just last name) since loosening DOB raises collision risk
--         more than Tier C does.
--   Tiebreak - when Tiers A-D together yield >1 distinct student_number for
--         a gap, narrow using first_name (case-fold/diacritic-strip, plus
--         stripping non-alphanumeric characters so an apostrophe like
--         "E'Nylah" doesn't block the match).
--
-- Tier C/D corroboration (Tier A/B skip both - already tight enough):
--   gender_ok  - HARD GATE. Compare CB gender vs PS gender for the matched
--                student_number + academic_year. No legitimate reason to
--                differ; a mismatch routes the row to flagged_for_review
--                instead of resolved.
--   enrolled_in_matching_course - INFORMATIONAL ONLY, never a gate. Checks
--                whether the matched student was enrolled in the course
--                matching the exam. Can't reuse int_collegeboard__ap_unpivot
--                (it requires prior crosswalk resolution - exactly what's
--                being checked - so an unresolved candidate is invisible to
--                it); instead unpivots exam codes directly off
--                stg_collegeboard__ap for just the Tier C/D candidates.
--                Joins on ap_course_subject (NOT cc_course_number, a plain
--                PS course code like "ENG01005C3" that never matches),
--                filtered to rn_course_number_year=1 and not
--                is_dropped_section, bridged across district-union tables
--                via _dbt_source_relation region-matching (studentid values
--                aren't globally unique across districts). Presence
--                corroborates; absence proves nothing (testing without the
--                class, and vice versa, is normal - CB doesn't require
--                course enrollment to sit the exam).
--
-- No fuzzy/similarity matching anywhere - every transform above is a
-- deterministic string operation.

with gaps as (
  select
    a.ap_number_ap_id,
    a.first_name as cb_first_name,
    a.last_name as cb_last_name,
    a.date_of_birth as cb_dob,
    a.gender as cb_gender,
    a.enrollment_school_year
  from `teamster-332318`.kipptaf_collegeboard.stg_collegeboard__ap a
  inner join `teamster-332318`.kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves u
    on a.ap_number_ap_id = u.ap_number_ap_id
),
ps as (
  select distinct
    student_number, studentid, first_name, last_name, dob, gender, academic_year, _dbt_source_relation,
    regexp_replace(normalize(upper(last_name), nfd), r"\pM", "") as last_name_stripped,
    regexp_replace(regexp_replace(normalize(upper(first_name), nfd), r"\pM", ""), r"[^A-Z0-9]", "") as first_name_norm,
    split(regexp_replace(regexp_replace(normalize(upper(last_name), nfd), r"\pM", ""), "-", " "), " ") as last_name_tok
  from `teamster-332318`.kipptaf_powerschool.base_powerschool__student_enrollments
),
gaps_norm as (
  select *,
    regexp_replace(regexp_replace(normalize(upper(cb_first_name), nfd), r"\pM", ""), r"[^A-Z0-9]", "") as cb_first_name_norm,
    split(regexp_replace(regexp_replace(normalize(upper(cb_last_name), nfd), r"\pM", ""), "-", " "), " ") as cb_last_name_tok
  from gaps
),
tier_ab as (
  select g.ap_number_ap_id, p.student_number, 'A_B' as tier
  from gaps_norm g
  join ps p
    on p.academic_year = g.enrollment_school_year
    and p.dob = g.cb_dob
    and (upper(p.last_name) = upper(g.cb_last_name) or p.last_name_stripped = regexp_replace(normalize(upper(g.cb_last_name), nfd), r"\pM", ""))
),
tier_c_raw as (
  select g.ap_number_ap_id, p.student_number, t1, t2
  from gaps_norm g
  join ps p
    on p.academic_year = g.enrollment_school_year
    and p.dob = g.cb_dob
  cross join unnest(p.last_name_tok) as t1
  cross join unnest(g.cb_last_name_tok) as t2
),
tier_c as (
  select distinct ap_number_ap_id, student_number, 'C' as tier
  from tier_c_raw
  where t1 = t2
),
tier_d as (
  select g.ap_number_ap_id, p.student_number, 'D' as tier
  from gaps_norm g
  join ps p
    on p.academic_year = g.enrollment_school_year
    and abs(date_diff(p.dob, g.cb_dob, day)) in (365, 366)
    and (upper(p.last_name) = upper(g.cb_last_name) or p.last_name_stripped = regexp_replace(normalize(upper(g.cb_last_name), nfd), r"\pM", ""))
    and p.first_name_norm = g.cb_first_name_norm
),
all_tiers as (
  select * from tier_ab union all select * from tier_c union all select * from tier_d
),
combined as (
  select ap_number_ap_id, student_number, string_agg(distinct tier order by tier) as tiers
  from all_tiers
  group by 1, 2
),
tiebreak as (
  select c.ap_number_ap_id, c.student_number, c.tiers
  from combined c
  join gaps_norm g on g.ap_number_ap_id = c.ap_number_ap_id
  join ps p on p.student_number = c.student_number
  where p.first_name_norm = g.cb_first_name_norm
),
per_gap as (
  select g.ap_number_ap_id, count(distinct c.student_number) as n_combined
  from gaps_norm g
  left join combined c on c.ap_number_ap_id = g.ap_number_ap_id
  group by 1
),
resolved_candidate as (
  select
    pg.ap_number_ap_id,
    case
      when pg.n_combined = 1 then (select any_value(student_number) from combined c where c.ap_number_ap_id = pg.ap_number_ap_id)
      else (select any_value(student_number) from tiebreak t where t.ap_number_ap_id = pg.ap_number_ap_id)
    end as student_number,
    case
      when pg.n_combined = 1 then (select any_value(tiers) from combined c where c.ap_number_ap_id = pg.ap_number_ap_id)
      else (select any_value(tiers) from tiebreak t where t.ap_number_ap_id = pg.ap_number_ap_id)
    end as tiers
  from per_gap pg
  where pg.n_combined >= 1
    and (pg.n_combined = 1 or (select count(distinct student_number) from tiebreak t where t.ap_number_ap_id = pg.ap_number_ap_id) = 1)
),
with_gender_check as (
  select
    rc.ap_number_ap_id, rc.student_number, rc.tiers, g.enrollment_school_year,
    case when rc.tiers = 'A_B' then true else g.cb_gender = p.gender end as gender_ok
  from resolved_candidate rc
  join gaps_norm g on g.ap_number_ap_id = rc.ap_number_ap_id
  join ps p on p.student_number = rc.student_number and p.academic_year = g.enrollment_school_year
),
cd_candidates as (
  select ap_number_ap_id, student_number, enrollment_school_year
  from with_gender_check
  where tiers != 'A_B' and gender_ok
),
raw_unpivot as (
  select ap_number_ap_id, exam_code
  from `teamster-332318`.kipptaf_collegeboard.stg_collegeboard__ap
  unpivot (
    (exam_code) for rn_exam_number in (
      exam_code_01, exam_code_02, exam_code_03, exam_code_04, exam_code_05,
      exam_code_06, exam_code_07, exam_code_08, exam_code_09, exam_code_10,
      exam_code_11, exam_code_12, exam_code_13, exam_code_14, exam_code_15,
      exam_code_16, exam_code_17, exam_code_18, exam_code_19, exam_code_20,
      exam_code_21, exam_code_22, exam_code_23, exam_code_24, exam_code_25,
      exam_code_26, exam_code_27, exam_code_28, exam_code_29, exam_code_30
    )
  )
  where ap_number_ap_id in (select ap_number_ap_id from cd_candidates)
),
exam_to_course as (
  select distinct u.ap_number_ap_id, p as ps_ap_course_subject_code
  from raw_unpivot u
  join `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__collegeboard__ap_codes c1
    on u.exam_code = c1.code and c1.`domain` = 'Exam Codes'
  join `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__collegeboard__ap_course_crosswalk xw
    on c1.description = xw.test_name and xw.data_source = 'CB File'
  cross join unnest(split(xw.ps_ap_course_subject_code, ',')) as p
),
course_bridge as (
  select cc.ap_number_ap_id, cc.enrollment_school_year, p.studentid as ps_internal_studentid, p._dbt_source_relation
  from cd_candidates cc
  join ps p on p.student_number = cc.student_number and p.academic_year = cc.enrollment_school_year
),
course_enrollment_check as (
  select etc.ap_number_ap_id, logical_or(ce.ap_course_subject is not null) as enrolled_in_matching_course
  from exam_to_course etc
  join course_bridge cb on cb.ap_number_ap_id = etc.ap_number_ap_id
  left join `teamster-332318`.kipptaf_powerschool.base_powerschool__course_enrollments ce
    on ce.cc_studentid = cb.ps_internal_studentid
    and ce.cc_academic_year = cb.enrollment_school_year
    and regexp_extract(ce._dbt_source_relation, r'(kipp\w+)_') = regexp_extract(cb._dbt_source_relation, r'(kipp\w+)_')
    and ce.rn_course_number_year = 1
    and not ce.is_dropped_section
    and ce.ap_course_subject = etc.ps_ap_course_subject_code
  group by 1
)
select
  wgc.ap_number_ap_id,
  wgc.student_number,
  wgc.tiers,
  if(not wgc.gender_ok, 'flagged_for_review', 'resolved') as bucket,
  cec.enrolled_in_matching_course
from with_gender_check wgc
left join course_enrollment_check cec on cec.ap_number_ap_id = wgc.ap_number_ap_id
union all
select g.ap_number_ap_id, cast(null as int64), cast(null as string), 'no_match', cast(null as bool)
from gaps_norm g
where not exists (select 1 from resolved_candidate rc where rc.ap_number_ap_id = g.ap_number_ap_id)
order by bucket, ap_number_ap_id
```

- [ ] **Step 2: Run it via the BigQuery MCP `execute_sql` tool**

Expected: empty result once the crosswalk is fully caught up (validated: `0`
rows against the current, fully-resolved 2025-2026 backlog — this is correct
behavior, not a bug). Against an actual backlog, expect a mix of `resolved` /
`flagged_for_review` / `no_match` rows (validated against the 173-gap 2025-2026
backlog: 173 `resolved`, 0 `flagged_for_review`, 0 `no_match`, after Tiers C/D
were added).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/collegeboard-ap-data-ingest-protocol/queries/03-tiered-crosswalk-match.sql
git commit -m "feat: add tiered crosswalk match query to AP ingest protocol skill"
```

## Task 4: Downstream Lineage Query

**Files:**

- Create:
  `.claude/skills/collegeboard-ap-data-ingest-protocol/queries/04-downstream-lineage.sql`

**Interfaces:**

- Consumes:
  `kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves`,
  `kipptaf_collegeboard.int_collegeboard__ap_unpivot`,
  `kipptaf_tableau.rpt_tableau__ap_assessment_dashboard`
- Produces: a one-row count summary, then (if counts don't reconcile) rows of
  `(powerschool_student_number, exam_code_description, ps_ap_course_subject_code, ap_course_name)`
  for exam scores present in `int_collegeboard__ap_unpivot` but missing from the
  dashboard

- [ ] **Step 1: Write the query**

```sql
-- Downstream Lineage Verification
--
-- Confirms a crosswalk fix actually reaches int_collegeboard__ap_unpivot and
-- the CARAT dashboard (rpt_tableau__ap_assessment_dashboard), not just the
-- crosswalk sheet. rpt_tableau__ap_assessment_dashboard lives in the
-- kipptaf_tableau dataset (not a generic "extracts" dataset - confirmed via
-- INFORMATION_SCHEMA, don't guess). The dashboard's actual Tableau workbook
-- is the "College Admission Readiness Assessments Tracker (CARAT)" exposure
-- in src/dbt/kipptaf/models/exposures/tableau.yml
-- (name: college_admission_readiness_assessments_tracker_carat, LSID
-- 286156c4-2f9e-4983-926b-63c9b11f44f4, Dagster-owned refresh cron
-- "0 6 * * *") - use the exposure file to find the workbook, don't guess at
-- names. Since the BQ table is a live VIEW, this count comparison already
-- reflects what a live Tableau connection would show; only cross-check via
-- the Tableau MCP (get-workbook / list-datasources with the LSID) if the
-- workbook turns out to use an extract instead.
--
-- Replace <academic_year> below with the year the crosswalk fix targeted.

select
  (select count(*) from `teamster-332318`.kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves) as remaining_crosswalk_gaps,
  (select count(*) from `teamster-332318`.kipptaf_collegeboard.int_collegeboard__ap_unpivot where academic_year = <academic_year>) as unpivot_rows,
  (select count(*) from `teamster-332318`.kipptaf_tableau.rpt_tableau__ap_assessment_dashboard where academic_year = <academic_year> and test_name is not null) as dashboard_scored_rows;

-- If unpivot_rows and dashboard_scored_rows don't reconcile, find exactly
-- which exam scores are missing from the dashboard:

select
  u.powerschool_student_number,
  u.exam_code_description,
  u.ps_ap_course_subject_code,
  u.ap_course_name
from `teamster-332318`.kipptaf_collegeboard.int_collegeboard__ap_unpivot u
where u.academic_year = <academic_year>
  and not exists (
    select 1
    from `teamster-332318`.kipptaf_tableau.rpt_tableau__ap_assessment_dashboard d
    where d.academic_year = <academic_year>
      and d.student_number = u.powerschool_student_number
      and d.ps_ap_course_subject_code = u.ps_ap_course_subject_code
      and d.test_name is not null
  );

-- For each missing row, check whether the student has ANY course enrollment
-- with a matching ap_course_subject (regardless of the dashboard's specific
-- join filters) to distinguish "PowerSchool tagging gap" (a sibling course
-- with the right subject exists but wasn't picked up - see
-- 02-ap-course-tagging.sql) from "genuinely tested without taking the class"
-- (a real, expected scenario per College Board's rules - not a bug to
-- chase; if EVERY missing row is this case, the root cause is actually
-- rpt_tableau__ap_assessment_dashboard's join structure itself - see
-- https://github.com/TEAMSchools/teamster/issues/4391):

select
  se.student_number, ce.ap_course_subject, ce.courses_course_name, ce.is_dropped_section
from `teamster-332318`.kipptaf_powerschool.base_powerschool__course_enrollments ce
join `teamster-332318`.kipptaf_powerschool.base_powerschool__student_enrollments se
  on se.studentid = ce.cc_studentid
  and se.academic_year = ce.cc_academic_year
  and regexp_extract(se._dbt_source_relation, r'(kipp\w+)_') = regexp_extract(ce._dbt_source_relation, r'(kipp\w+)_')
where se.student_number in (<missing_student_numbers>)
  and ce.cc_academic_year = <academic_year>
  and ce.ap_course_subject is not null
```

- [ ] **Step 2: Run it via the BigQuery MCP `execute_sql` tool**, substituting
      the actual target academic year for `<academic_year>`

Expected (validated for `academic_year = 2025`, 2025-2026 admin, after the
crosswalk fix): `remaining_crosswalk_gaps = 0`, `unpivot_rows = 658`,
`dashboard_scored_rows = 643`. The 15-row gap traced to two causes: 12
Seminar-exam rows (the `ENG22110C4` tagging gap from Task 2), 3 rows that are
the `rpt_tableau__ap_assessment_dashboard` join-structure bug (issue #4391) —
students who genuinely tested without a matching course enrollment. Future runs
will show different counts; the query's job is to surface whatever the real gap
is, not reproduce these exact numbers.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/collegeboard-ap-data-ingest-protocol/queries/04-downstream-lineage.sql
git commit -m "feat: add downstream lineage query to AP ingest protocol skill"
```

## Task 5: SKILL.md Runbook

**Files:**

- Create: `.claude/skills/collegeboard-ap-data-ingest-protocol/SKILL.md`

**Interfaces:**

- Consumes: all four query files from Tasks 1-4; Dagster MCP tools
  (`get_asset_health`, `get_asset_materializations`, `launch_run`); BigQuery MCP
  `execute_sql`
- Produces: the full 13-phase runbook a fresh agent follows end-to-end

- [ ] **Step 1: Write the file**

```markdown
---
name: collegeboard-ap-data-ingest-protocol
description:
  Use when resolving gaps in the College Board AP ID crosswalk, when new AP
  scores aren't showing up on the AP assessment / CARAT dashboard, when
  stg_collegeboard__ap hasn't picked up a new AP score file drop, or when
  auditing the AP codes/course-crosswalk sheets for completeness.
---

# College Board AP Data Ingest Protocol

## Overview

Every AP admin year, new scores land in `stg_collegeboard__ap` but silently fail
to reach `rpt_tableau__ap_assessment_dashboard` (the CARAT dashboard) for one of
four reasons: the staging table hasn't picked up the new file, new students
aren't in the CB-ID-to-PowerSchool crosswalk sheet yet, the
codes/course-crosswalk sheets are missing an entry, or a crosswalk fix doesn't
fully propagate downstream. This skill walks all four, in order, with the human
approving every risky action and every batch of data before it moves.

**Full design rationale and validation evidence:**
`docs/superpowers/specs/2026-07-13-collegeboard-ap-pipeline-audit-design.md`.
This file is the runbook; that doc is the "why."

## PII — read this before running anything

Crosswalk-matching results (Phases 4-8) include student names, DOB, and gender.
**Never write these to any file that gets committed to git** — issue, PR, commit
message, or any file under version control. Chat/terminal output only. The
codes-completeness, AP-course-tagging, and downstream-lineage checks carry no
PII (codes, course names, aggregate counts) — no special handling needed for
those.

## Why crosswalk gaps happen (say this to the user)

A College Board ID can be missing from the crosswalk sheet for two reasons: a
first-time AP tester (no ID ever existed to add), or a student with a second CB
account for this admin (College Board's merge process is too tedious for KTAF to
pursue — the fix is just adding the new ID as another mapping to the same
`student_number`). Both resolve identically (add the row) — say this out loud
when presenting results so a "new" ID doesn't read as something having gone
wrong.

## Phase 1: Ingestion check

Compare materialization timestamps via `get_asset_health` /
`get_asset_materializations`: raw `kipptaf/collegeboard/ap` (partitioned by
school × school_year) vs. staging `kipptaf/collegeboard/stg_collegeboard__ap`.

If a raw partition materialized more recently than staging's last
materialization, staging is stale — most likely blocked by
`stg_collegeboard__ap`'s automation condition, whose partition range extends to
`CURRENT_FISCAL_YEAR.fiscal_year + 1`, a partition that's always unmaterialized
and trips the condition's `not (any_deps_missing)` gate. This recurs every year
until that automation condition itself is fixed (separate issue, not this
skill's job).

**Always ask before launching anything.** Preview with
`launch_run(..., confirm=False)`, explain to the user why (which partitions are
newer, and that the automation condition is blocking the rebuild), then fire
with `confirm=True` only after explicit approval. Never skip the ask, even
though this is expected to recur annually.

After the run succeeds, re-check asset health. `int_collegeboard__ap_unpivot`
doesn't need a separate manual trigger — it rematerializes on its own via the
automation condition once `stg_collegeboard__ap` succeeds.

Only proceed to Phase 2 once staging is confirmed fresh.

## Phase 2: Codes completeness check

Run [`queries/01-codes-completeness.sql`](queries/01-codes-completeness.sql).

If it returns any rows: for each missing code, look up its meaning by fetching
(reading the actual document, not trusting a search-result summary) the current
College Board "AP Student Datafile for Schools and Districts [Year] Layout
Format" PDF at `apcentral.collegeboard.org`. Hand the user the missing code, its
looked-up description, and the direct sheet URL:
`https://docs.google.com/spreadsheets/d/1dmPEB3lVBwNhcGANh1H8_D42nK3zIrFFE0rBFZQBuxE`
(tab `src_collegeboard__ap_codes`) so they can add it manually — no Sheets write
access here.

## Phase 3: AP course tagging check

Run [`queries/02-ap-course-tagging.sql`](queries/02-ap-course-tagging.sql).

Any row returned is a PowerSchool course-setup gap — flag it unconditionally
(regardless of whether it happens to matter to this cycle's matching). If found,
identify the owning region/district with the follow-up query in that file's
comments, and hand the finding to whoever owns PowerSchool course setup for that
region. No write access to PowerSchool here.

## Phase 4: Pre-audit summary

Get cheap counts before running anything expensive:

- Total raw students: `stg_collegeboard__ap` row count for the relevant admin
  year.
- Total exam scores: `int_collegeboard__ap_unpivot` row count for the same year.
- Gap count:
  `select count(*) from kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves`.

Present as: "The raw AP file has _N_ students resolving to _M_ exam scores. Of
those, _G_ aren't in the crosswalk yet." Then ask: "Ready for me to run the
matching audit against PowerSchool?" **Don't proceed without confirmation.**

## Phase 5: Run the tiered match

Run
[`queries/03-tiered-crosswalk-match.sql`](queries/03-tiered-crosswalk-match.sql)
once approved. This already includes the Tier C/D corroboration checks (gender
hard-gate, course-enrollment informational annotation) — see the comments in
that file for the full tier/corroboration logic.

## Phase 6: Tier breakdown

Present counts per tier (how many resolved at Tier A/B, C, D, via tiebreak), how
many `flagged_for_review` (gender mismatch), and how many `no_match`. Ask:
"Ready to start copy-pasting matches into the sheet?" **Don't proceed without
confirmation.**

## Phase 7: Batch-by-batch delivery

Present `resolved` rows in batches of 20, **as a plain delimited block in a
fenced code block** (`College_Board_ID<tab>PowerSchool_Student_Number`, one pair
per line) — not a markdown table, so it pastes cleanly into two Sheet columns
without pipe/dash characters riding along. If a batch contains any Tier C/D
rows, put a small markdown review table (tier tag, course-enrollment note)
immediately above the paste block for eyeballing — not for pasting.

After each batch, ask "Ready for the next batch?" and wait — **never dump all
batches in one message.**

Present `flagged_for_review` rows (if any) separately, after all `resolved`
batches, as a markdown table (CB first/last/gender vs. PS first/last/gender) for
the user to decide on individually — these never go in a paste block.

Present `no_match` rows (if any) as a single markdown table (CB first/last/DOB)
— see Phase 13.

The Google Sheet itself:
`https://docs.google.com/spreadsheets/d/1dmPEB3lVBwNhcGANh1H8_D42nK3zIrFFE0rBFZQBuxE`
(tab `src_collegeboard__ap_id_crosswalk`).

## Phase 8: User pastes

The user manually pastes each batch's rows into the Google Sheet — as they go,
or after the last batch, whichever they prefer. No tool here can write to Sheets
directly.

## Phase 9: Post-paste reconciliation

Once the last batch is delivered, watch
`stg_google_sheets__collegeboard__ap_id_crosswalk`'s row count (Dagster asset
health, or a direct BigQuery row count) until it increases by the number of
resolved rows generated. Tell the user explicitly that a reconciliation check is
about to run, then compare the generated `resolved` list against the actual new
rows in that table:

- **Missing rows** — a generated pair that never made it in.
- **Duplicate rows** — the same `College_Board_ID` appearing more than once,
  possibly with different student numbers.
- **Incorrect rows** — a `College_Board_ID` present with a different
  `student_number` than generated.

## Phase 10: Downstream lineage verification

Once the sheet reconciles cleanly, run
[`queries/04-downstream-lineage.sql`](queries/04-downstream-lineage.sql)
(substituting the target academic year) and present the before/after count
summary across crosswalk sheet → `int_collegeboard__ap_unpivot` → dashboard. If
counts don't reconcile, use the file's follow-up queries to find exactly which
rows are missing and why (a PowerSchool tagging gap vs. the known dashboard
join-structure limitation, tracked in
[#4391](https://github.com/TEAMSchools/teamster/issues/4391)).

## Phase 11: Final gap recount

Re-run the Phase 4 gap-count query to confirm it dropped to the expected
residual (0 for a fully-resolved run, or the remaining `no_match` count
otherwise).

## Phase 12: No-match root cause review

For whatever remains in `no_match`, don't just hand it over — characterize _why_
it didn't match, in chat only (never write real names/DOB to a committed file):

1. Loosen the DOB constraint (any academic_year, not just the gap's own year)
   and look for the same last_name/token — reveals students who exist under a
   different year.
2. Loosen the last_name constraint (same DOB, any last_name in the same year) —
   reveals a name recorded very differently.
3. If a case reveals a new deterministic, generalizable pattern (not one-off
   noise), that's a signal a new tier belongs in `03-tiered-crosswalk-match.sql`
   — the same way Tiers C and D were derived during design. Genuinely one-off
   cases (student really isn't in PowerSchool) stay manual.

This is diagnostic, not a promise to keep expanding tiers forever — the goal is
a small manual-review bucket and evidence-based future additions.
```

- [ ] **Step 2: Verify frontmatter and word count**

```bash
uv run --with pyyaml python -c "
import yaml, pathlib
text = pathlib.Path('.claude/skills/collegeboard-ap-data-ingest-protocol/SKILL.md').read_text()
front = text.split('---')[1]
meta = yaml.safe_load(front)
assert set(meta) >= {'name', 'description'}
assert len(front) <= 1024
print('frontmatter OK:', meta['name'])
"
wc -w .claude/skills/collegeboard-ap-data-ingest-protocol/SKILL.md
```

Expected: `frontmatter OK: collegeboard-ap-data-ingest-protocol` and a word
count (this skill is intentionally longer than the <500-word guideline for
frequently-loaded skills — it's a domain-specific, occasionally-invoked 13-phase
runbook, not a getting-started skill).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/collegeboard-ap-data-ingest-protocol/SKILL.md
git commit -m "feat: add SKILL.md runbook for AP data ingest protocol"
```

## Task 6: End-to-End Validation

**Files:** none created — this task exercises Tasks 1-5's output.

**Interfaces:**

- Consumes: the full skill directory from Tasks 1-5
- Produces: a pass/fail judgment on whether a fresh agent can correctly follow
  the runbook

- [ ] **Step 1: Dispatch a fresh subagent with only the skill's content** (no
      memory of this conversation), prompted to: "Using
      `.claude/skills/collegeboard-ap-data-ingest-protocol/SKILL.md`, check
      whether the College Board AP crosswalk pipeline has any current gaps and
      walk me through resolving them if so." Give it BigQuery MCP and Dagster
      MCP tool access; explicitly instruct it NOT to actually launch any Dagster
      run (`confirm=True`) or take any other real action — dry-run only,
      reporting what it would do at each phase.

- [ ] **Step 2: Confirm the subagent's behavior matches these three criteria**
      (this is the Technique-skill validation, per superpowers:writing-skills —
      "can it apply the technique correctly"):
  - It runs Phase 1 (ingestion check) before anything else, and — since the real
    pipeline is currently caught up — correctly reports no staleness rather than
    inventing a run to launch.
  - It runs Phases 2-3 (codes/course-tagging checks) and reports the real,
    current results (0 codes gaps; the one `ENG22110C4` course-tagging gap, if
    it's still unresolved at run time) rather than hallucinating different
    numbers.
  - Since the crosswalk is currently fully resolved (0 gaps), it correctly
    reports a clean state at Phase 4 and does not fabricate a matching exercise
    or ask to paste anything — it should recognize "0 gaps, nothing to do" as a
    valid, complete outcome, not treat the runbook's later phases as mandatory
    busywork.
  - It never proposes writing any student name, DOB, or gender value into a
    file, issue, or commit.

- [ ] **Step 3: If any criterion fails**, fix the SKILL.md wording (not the
      underlying queries — those are independently validated in Tasks 1-4) and
      re-dispatch. Do not mark this task done until a subagent run satisfies all
      three.

## Task 7: Final Lint and Push

**Files:** none created.

- [ ] **Step 1: Run trunk check on every new file**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  .claude/skills/collegeboard-ap-data-ingest-protocol/SKILL.md \
  .claude/skills/collegeboard-ap-data-ingest-protocol/queries/01-codes-completeness.sql \
  .claude/skills/collegeboard-ap-data-ingest-protocol/queries/02-ap-course-tagging.sql \
  .claude/skills/collegeboard-ap-data-ingest-protocol/queries/03-tiered-crosswalk-match.sql \
  .claude/skills/collegeboard-ap-data-ingest-protocol/queries/04-downstream-lineage.sql
```

Expected: no findings (or only auto-fixed formatting). `.sql` files here are
ad-hoc operational queries for a skill, not dbt models — the `src/dbt/CLAUDE.md`
SQL style guide (no correlated subqueries, no `ORDER BY`, etc.) does not apply
to this directory.

- [ ] **Step 2: Push**

```bash
git push
```

- [ ] **Step 3: Update the tracking issue.** Comment on
      [#4390](https://github.com/TEAMSchools/teamster/issues/4390) that the
      skill is implemented and validated, linking the final commit.
