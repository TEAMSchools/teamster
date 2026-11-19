# NJ SLEDS Student Management: candidate dbt tests

Draft for the data team planning session, 2026-10-20. Builds on
`student-management-fields.md` (the element rules),
`existing-tests-inventory.md`, `powerschool-ingestion-gaps.md`,
`cds-fix/scripts/njsleds_flags.py`, and the #5558 design ("What backs up a
ticketed test"). No student data appears here. The warehouse facts below are
aggregate counts of currently enrolled NJ students, rounded.

Everything in the "host", "test form", "fix owner" and defense columns is a
**proposal**. Rules, citations and warehouse facts are facts.

## How to read this

### Hosts

Per #5558 step 1, the ticketed test sits at `severity: warn` on the earliest
model carrying record id, school, region and period. The powerschool package
builds once per NJ district, so the district project supplies the region. NJ
districts materialize package models as tables
(`powerschool: +materialized: table`), so package hosts do not go dormant.

| Code                    | Model                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Status    |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `ps.enr`                | package `int_powerschool__student_enrollment_union`. Stint grain, with `student_number`, `schoolid`, `academic_year`, `rn_all`, `year_in_network`, and the students-table identity columns (`state_studentnumber`, names, `dob`, `gender`, `fedethnicity`, `ethnicity`, `entrycode`, `exitcode`, `lunchstatus`, `city`). Drops no-shows (`exitdate > entrydate`).                                                                                                                                                                                                                                                 | exists    |
| `ps.stu`                | package `stg_powerschool__students`. Has `schoolid` but no period column. Used only where `ps.enr` filters the rows out, or for district-wide uniqueness.                                                                                                                                                                                                                                                                                                                                                                                                                                                         | exists    |
| `ps.njx`                | **PROPOSED** package int at stint grain: `ps.enr` plus `stg_powerschool__s_nj_stu_x` (latest stint), `stg_powerschool__s_nj_ren_x` (re-enrollment stints, for the columns it carries), `stg_powerschool__studentcorefields`, `stg_powerschool__s_stu_x`, and the students-table `districtentrydate` / `schoolentrydate`. It would apply the PS-R override-else-fallback logic. No package model joins `s_nj_stu_x` to school and period today. The nearest is kipptaf `int_students__student_enrollments`, which is a view (tests would go dormant) and carries about 20 of the roughly 60 `s_nj` columns needed. | not built |
| `ps.race`               | **PROPOSED** singular test: `ps.enr` left join `stg_powerschool__studentrace` on `studentid`. It needs `meta.dagster.ref` with `package: powerschool`.                                                                                                                                                                                                                                                                                                                                                                                                                                                            | not built |
| `kt.seu`                | kipptaf `int_students__student_enrollment_union` (table, cross-region, `_dbt_source_project`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | exists    |
| `kt.aut` / `kt.aut_iep` | kipptaf `rpt_powerschool__autocomm_students` / `_iep`: the data team's feeds that write state fields into PowerSchool                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | exists    |
| `kt.gpc`                | kipptaf `int_students__graduation_path_codes`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | exists    |

Package-hosted ticketed tests must set `severity: warn` explicitly, because the
package default is `error`.

### Shorthand used in predicates

- `d` = report date: Fall cutoff 2026-10-15, EOY 2027-06-30, or the run date
  (see E-5).
- **CY** = `academic_year = var('current_academic_year') and grade_level != 99`.
- **CUR** = `rn_all = 1`. Use it for fields PowerSchool stores once per student
  (`s_nj_stu_x`, `studentcorefields`, students identity). It gives one ticket
  row per student, not one per historical stint, and the history of these fields
  is overwritten anyway.
- **ACT** = CY and `entrydate <= d and exitdate > d`. **INACT** = CY and
  `exitdate <= d`. **G12** = `grade_level = 12`.
- `blank(x)` = `nullif(trim(x), '') is null`.
- `rep_first` =
  `coalesce(nullif(trim(pscore_legal_first_name), ''), first_name)`; likewise
  `rep_middle` and `rep_last`. `rep_suffix` =
  `coalesce(nullif(trim(generationcodesuffix), ''), pscore_legal_suffix)`. PS-R
  #3-6: the report sends the legal name when it is filled in and appends the
  suffix to the last name.
- **USB** (US-born for birthplace rules) =
  `coalesce(ltrim(countryofbirth, '0'), '2330') = '2330'`. A blank country
  counts because PS sends "USA". **USPR** = USB or
  `ltrim(countryofbirth, '0') = '1790'`. **FB** = not USPR and
  `countryofbirth != 'R'`. **REF** = `birthplace_refusal = '1'` or any
  birthplace field = 'R'.

### Other columns

- **Test form:** `nn` not_null, `av` accepted_values, `rel` relationships,
  `expr` dbt_utils.expression_is_true, `ucc` unique_combination_of_columns,
  `sing` singular. "+ where" means a `config.where` scope.
- **Fix owner:** REG school registrar, OPS school ops, CMP Compliance, SRE
  SRE-enrollment, DT data team.
- **Source-fixable:** Y means a PowerSchool (or EdPlan or Finalsite) edit clears
  it, so it is ticketable under #5558. N means the value is written by data-team
  code (autocomm) or is correct at source. An N failure is a code fix with an
  error-level test, not a ticket.
- **Prereqs:** `LKP:` a lookup table (Section B); `GAP:` the PowerSchool table
  or column is not ingested; `CONFIRM:` the source column or PowerSchool
  behavior is unverified; `var:` needs a submission-window variable.
- **Overlap:** `A#` is a check in `rpt_tableau__student_info_audit`; `NF` is a
  rule in `njsleds_flags.py`; `T:` is an existing dbt test.
- **Confidence** that this is a real state rejection rule:
  - **H**: the handbook says "error" ([E] or a system [CE] message), or
    njsleds_flags marks it "state rejects".
  - **M**: a "must" Validation Check [VC], an Additional Note [AN], a template
    rule, or a KTAF-specific inference.
  - **L**: a handbook Warning [W] (not a rejection), a plausibility check, or
    KTAF's internal entry-code mapping.

### Warehouse facts that shaped the rows (2026-10-20, about 9.6k enrolled NJ students)

These are aggregate counts with no student rows.

- **Mostly blank PowerSchool fields.** The handbook makes all of these
  mandatory, so either PowerSchool defaults them on output or they reject (E-1):
  - `titleiindicator`: about 98% blank
  - `alternativeeducationprogram_yn`: about 100% blank
  - `homeless_code` (studentcorefields): about 87% blank
  - `gifted_and_talented`: about 83% blank
  - `home_language`: about 76% blank
  - `military_connected_indicator`: about 9% blank
  - `includeinnjsmart_tf`: blank for about 99.6%, even though PS-R lists it as a
    selection criterion.
- `districtentrydate` and `schoolentrydate` are identical for 100% of enrolled
  students, because autocomm writes both from the district entry date. About 60
  carry the 1899/1900 placeholder.
- **SIDs:** under 30 enrolled students have none; every other SID is 10 digits.
- **CDS codes:** all nine CDS columns have the correct width for enrolled
  students. The Camden short-code issue noted on 10/8 is gone. About 30 have
  blank resident overrides, about 10 have blank attending/receiving overrides,
  and fewer than 10 resident school codes are 2 characters.
- **Birthplace and immigrant status:** about 190 country-of-birth codes have 3
  digits. `immigrantstatus_yn` mixes Y/N with 0/1 (about 14% are 0/1).
- **Exit codes:** values outside the state list appear in history: T1, G1, PR,
  TO, RE, TS, and D2 (D2 was removed, HB p.27). Fewer than 10 current-year
  stints carry T1. Graduates are stored as G1, not L.
- **Entry codes:** values outside the list appear in history: P, OE, R, RT, T1.
  The current year has none outside the list and fewer than 10 blanks. R13 is on
  about 320 current-year stints.
- **Ethnicity and gender:** a handful (under 10) of current-year stints have
  `fedethnicity = -1`, and a handful have a blank gender.
- `tuition_code` is stored as '7' (no leading zero) for over 99% of enrolled
  students; about 30 are blank.
- `gradelevelcode` is blank for all, so PowerSchool derives grade from
  `grade_level`. The `programtypecode` override is set for about 3%.
- `studentcorefields.graduation_year` differs from
  `students.sched_yearofgraduation` for about 63%.

---

## A. Candidate test table

### A.1 Population and record grain

| id    | rule (plain English)                                                                  | predicate                                                                    | state citation          | host                                                           | test form   | fix owner | source-fixable? | prereqs                           | overlap                                                                  | conf |
| ----- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------- | -------------------------------------------------------------- | ----------- | --------- | --------------- | --------------------------------- | ------------------------------------------------------------------------ | ---- |
| SM-01 | Every record has an LID; LIDs unique per district                                     | `student_number is not null`; unique `student_number` where `dcid >= 1`      | HB p.40 [E]; PS-R #1    | ps.stu                                                         | nn + unique | OPS       | Y               | none                              | T: pkg `id` unique (error); kipptaf union `student_number` unique (warn) | H    |
| SM-02 | One open stint per student at a time (2 open = 2 active records)                      | no stint whose `entrydate` falls inside another stint of the same student    | HB p.170 [E]; p.42      | ps.enr                                                         | sing        | OPS       | Y               | none                              | T: `..ps_enrollment_all__no_overlapping_stints` (warn)                   | H    |
| SM-03 | No duplicate stint on one entry date                                                  | unique (`student_number`, `academic_year`, `entrydate`)                      | HB p.170 [E]            | ps.enr                                                         | ucc         | OPS       | Y               | none                              | T: existing ucc on ps.enr; kt.seu dedupes                                | H    |
| SM-04 | A register change in the same school updates the stint; no same-day exit and re-entry | no `exitdate` equal to the next `entrydate` at the same `schoolid`           | WB p.13                 | ps.enr                                                         | sing        | REG       | Y               | none                              | T: `..student_enrollment_union_no_shared_stint_boundary` (warn)          | M    |
| SM-05 | No-shows are still reported: exit date = first day, with an exit code                 | `entrydate = exitdate` ⇒ `exitcode is not null` (students and reenrollments) | WB p.13                 | ps.stu + `stg_powerschool__reenrollments` (ps.enr drops these) | sing        | REG       | Y               | none                              | none                                                                     | M    |
| SM-06 | Every current-year stint in the Fall snapshot still exists at EOY (no deletions)      | CY stint keys as of Oct 15 ⊆ CY stint keys now                               | WB p.17; HB p.133, 175  | kt.seu                                                         | sing        | OPS       | Y               | new snapshot of CY stint keys     | none                                                                     | M    |
| SM-07 | Stints excluded from the extract are deliberate (review list, no ticket)              | `sid_excludeenrollment = 1`                                                  | PS-R Selection Criteria | ps.njx                                                         | expr        | CMP       | Y               | CONFIRM: PS selection logic (E-6) | none                                                                     | L    |

### A.2 State ID (SID)

| id    | rule (plain English)                                                                                | predicate                                                                               | state citation            | host         | test form  | fix owner | source-fixable? | prereqs | overlap                        | conf |
| ----- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------- | ------------ | ---------- | --------- | --------------- | ------- | ------------------------------ | ---- |
| SM-08 | Inactive current-year records have a SID                                                            | `state_studentnumber is not null` where INACT                                           | HB p.42 [E]               | ps.enr       | nn + where | CMP       | Y               | none    | A4 (presence, active only)     | H    |
| SM-09 | Active records keep their SID once assigned (a blank re-runs ID matching and can mint a second SID) | `state_studentnumber is not null` where ACT and `entrydate < d - 14` (grace period TBD) | UNR p.2; SID p.1; HB p.42 | ps.enr       | nn + where | CMP       | Y               | none    | A4                             | M    |
| SM-10 | SID is exactly 10 digits                                                                            | `regexp_contains(state_studentnumber, r'^\d{10}$')`                                     | HB p.42 [E]; PS-S         | ps.enr (CUR) | expr       | CMP       | Y               | none    | none (A4 checks presence only) | H    |
| SM-11 | No SID shared by two students in a region                                                           | 1 distinct `student_number` per non-null `state_studentnumber`                          | HB p.42 [E]               | ps.stu       | sing       | CMP       | Y               | none    | none                           | H    |
| SM-12 | No SID open in two KTAF regions on the same date                                                    | same `state_studentnumber`, overlapping stints, different `_dbt_source_project`         | HB p.42 [E]               | kt.seu       | sing       | CMP       | Y               | none    | none                           | H    |

### A.3 Names

| id    | rule (plain English)                                                                                                 | predicate                                                                                                        | state citation                      | host         | test form | fix owner | source-fixable? | prereqs | overlap                           | conf |
| ----- | -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------- | ------------ | --------- | --------- | --------------- | ------- | --------------------------------- | ---- |
| SM-13 | Reported first and last name not blank                                                                               | `not blank(rep_first) and not blank(rep_last)`                                                                   | HB p.43 [E]; p.45 (TMPL min 1)      | ps.njx (CUR) | expr      | REG       | Y               | none    | NF blank first/last               | H    |
| SM-14 | No period in first, middle or last name                                                                              | `not regexp_contains(concat(rep_first, rep_middle, rep_last), r'\.')`                                            | HB p.43-45 [E]                      | ps.njx (CUR) | expr      | REG       | Y               | none    | A1; NF period ("state rejects")   | H    |
| SM-15 | Names use only letters, spaces, apostrophes and hyphens                                                              | `regexp_contains(rep_x, r"^[A-Za-z' -]*$")` (accents: E-10)                                                      | HB p.43-45 [CE] "invalid character" | ps.njx (CUR) | expr      | REG       | Y               | none    | A1; NF digits/symbols             | M    |
| SM-16 | First and middle ≤ 30 characters; last + suffix ≤ 50                                                                 | `length(rep_first) <= 30 and length(rep_middle) <= 30 and length(trim(concat(rep_last, ' ', rep_suffix))) <= 50` | HB p.43-45 [CE]; PS-R #6            | ps.njx (CUR) | expr      | REG       | Y               | none    | NF lengths                        | H    |
| SM-17 | Suffix has no punctuation (it is appended to LastName, so a period fails SM-14)                                      | `not regexp_contains(rep_suffix, r'[^A-Za-z]')`                                                                  | HB p.46 [VC]; PS-R #6               | ps.njx (CUR) | expr      | REG       | Y               | none    | NF suffix punctuation             | H    |
| SM-18 | Suffix is a generation (Jr, II-V), ≤ 3 characters, not Sr, and not also typed into the last name                     | `upper(rep_suffix) in ('JR','II','III','IV','V')`; last name does not end in a generation                        | HB p.46 [VC]; PS-R #6 (length 3)    | ps.njx (CUR) | expr      | REG       | Y               | none    | NF suffix group                   | L    |
| SM-19 | No look-alike apostrophes (’ ‘ ʼ ´ ′, backtick), mis-encoded text (â€, Ã, Â, �), HTML entities, or "?" inside a name | regex per njsleds_flags                                                                                          | none (ID matching risk, UNR p.1)    | ps.njx (CUR) | expr      | REG       | Y               | none    | A1 (partial); NF apostrophe group | L    |
| SM-20 | No leading, trailing or double spaces                                                                                | `not regexp_contains(rep_x, r'^\s')`, same for `\s$` and `\s{2}`                                                 | none stated                         | ps.njx (CUR) | expr      | REG       | Y               | none    | A1 (double space); NF             | L    |
| SM-21 | No FNU/LNU placeholders; use "Unknown"                                                                               | `upper(rep_first) != 'FNU' and upper(rep_last) != 'LNU'`                                                         | HB p.43, 45 [W]                     | ps.njx (CUR) | expr      | REG       | Y               | none    | NF placeholder                    | L    |
| SM-22 | Legal name differs from the Demographics name (review only, no ticket)                                               | `not blank(pscore_legal_first_name) and pscore_legal_first_name != first_name`; same for middle and last         | PS-R #3-5                           | ps.njx (CUR) | expr      | REG       | Y               | none    | NF legal ≠ demographics           | L    |

### A.4 Gender and date of birth

| id    | rule (plain English)                      | predicate                                                                   | state citation | host         | test form | fix owner | source-fixable? | prereqs                                                   | overlap       | conf |
| ----- | ----------------------------------------- | --------------------------------------------------------------------------- | -------------- | ------------ | --------- | --------- | --------------- | --------------------------------------------------------- | ------------- | ---- |
| SM-23 | Gender present and M, F or X              | `gender in ('M','F','X')` + not_null                                        | HB p.47 [E]    | ps.enr (CUR) | nn + av   | REG       | Y               | CONFIRM: `gender_code` or `pscore_legal_gender` (PS-R #7) | A3 (presence) | H    |
| SM-24 | DOB present, not in the future, age 2-105 | `dob is not null and date_diff(d, dob, year) between 2 and 105`             | HB p.48 [E]    | ps.enr (CUR) | expr      | REG       | Y               | none                                                      | A5 (presence) | H    |
| SM-25 | K-12 student is age 2-22                  | `grade_level between 0 and 12` ⇒ `date_diff(d, dob, year) between 2 and 22` | HB p.87 [E]    | ps.enr (CY)  | expr      | REG       | Y               | none                                                      | none          | H    |

### A.5 Birthplace

| id    | rule (plain English)                                                        | predicate                                                                           | state citation         | host         | test form | fix owner | source-fixable? | prereqs                  | overlap                             | conf |
| ----- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ---------------------- | ------------ | --------- | --------- | --------------- | ------------------------ | ----------------------------------- | ---- |
| SM-26 | City, state and country of birth not all blank, unless refused              | `REF or not (blank(cityofbirth) and blank(stateofbirth) and blank(countryofbirth))` | HB p.49 [E]            | ps.njx (CUR) | expr      | REG       | Y               | none                     | NF all blank ("state rejects")      | H    |
| SM-27 | US-born: city of birth required                                             | `USB and not REF` ⇒ `not blank(cityofbirth)`                                        | HB p.49 [E]            | ps.njx (CUR) | expr      | REG       | Y               | none                     | NF ("state rejects")                | H    |
| SM-28 | US-born: state of birth required                                            | `USB and not REF` ⇒ `not blank(stateofbirth)`                                       | HB p.49 [E], p.51 [CE] | ps.njx (CUR) | expr      | REG       | Y               | none                     | NF ("state rejects")                | H    |
| SM-29 | Foreign-born: state of birth blank, except AS, FM, GU, MH, MP, PW, PR, VI   | `FB` ⇒ `blank(stateofbirth) or stateofbirth in (<territories>)`                     | HB p.49-51 [E]         | ps.njx (CUR) | expr      | REG       | Y               | none                     | NF foreign-born with a state        | H    |
| SM-30 | State of birth in the handbook list (50 states, DC, territories, AE, AP, R) | av on `upper(stateofbirth)`                                                         | HB p.50-51 [E]         | ps.njx (CUR) | av        | REG       | Y               | none (hardcode)          | NF invalid state code               | H    |
| SM-31 | Country of birth in the NCES list, or R                                     | `ltrim(countryofbirth, '0')` in the lookup                                          | HB p.52 [E]            | ps.njx (CUR) | rel       | REG       | Y               | LKP: country codes       | none                                | H    |
| SM-32 | Country of birth not blank (PS sends "USA", which is not a code)            | `not blank(countryofbirth)`                                                         | HB p.52 [E]; PS-R #11  | ps.njx (CUR) | nn        | REG       | Y               | CONFIRM: PS output (E-1) | NF country blank                    | M    |
| SM-33 | Country code keeps 4 digits                                                 | `length(countryofbirth) = 4 or countryofbirth = 'R'`                                | HB p.52 (Numeric 1-4)  | ps.njx (CUR) | expr      | REG       | Y               | none                     | NF leading zero ("likely accepted") | L    |
| SM-34 | City of birth has no punctuation                                            | `not regexp_contains(cityofbirth, r"[^A-Za-z '-]")` (hyphen/apostrophe: E-15)       | HB p.49 [E]            | ps.njx (CUR) | expr      | REG       | Y               | none                     | NF ("state rejects")                | H    |
| SM-35 | City of birth is not a country, US state or county                          | njsleds_flags regex lists                                                           | HB p.49 [AN]           | ps.njx (CUR) | expr      | REG       | Y               | none (lists in the test) | NF city is a country/state/county   | M    |

### A.6 Race and ethnicity

| id    | rule (plain English)                                                                 | predicate                                                               | state citation                   | host         | test form | fix owner            | source-fixable? | prereqs | overlap                    | conf |
| ----- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- | -------------------------------- | ------------ | --------- | -------------------- | --------------- | ------- | -------------------------- | ---- |
| SM-36 | Hispanic flag is 0 or 1 (no null, no -1)                                             | `fedethnicity in (0, 1)` + not_null                                     | HB p.54 [E]                      | ps.enr (CUR) | nn + av   | REG                  | Y               | none    | A7 (null only); NF not Y/N | H    |
| SM-37 | A non-Hispanic student has at least 1 race                                           | `fedethnicity = 0` ⇒ a `stg_powerschool__studentrace.racecd` row exists | HB p.54 [AN]; NF "state rejects" | ps.race      | sing      | REG (SRE root cause) | Y               | none    | A7 (partial); NF           | H    |
| SM-38 | Race codes are I, A, B, P or W                                                       | `racecd in ('I','A','B','P','W')`                                       | HB p.55-61; PS-R #13-17          | ps.race      | sing      | REG                  | Y               | none    | none                       | M    |
| SM-39 | Hispanic student with no race (accepted, but no race reported)                       | `fedethnicity = 1` and no race row                                      | NF ("accepted")                  | ps.race      | sing      | REG                  | Y               | none    | NF                         | L    |
| SM-40 | Race recorded only in legacy `ethnicity`, not `studentrace` (intake integration gap) | `ethnicity is not null` and no race row                                 | cds-fix HANDOFF (root cause)     | ps.race      | sing      | SRE                  | Y               | none    | A2, A7 (adjacent)          | L    |

### A.7 KTAF constants (charter, non-vocational)

| id    | rule (plain English)                                                                        | predicate                                | state citation         | host   | test form | fix owner | source-fixable? | prereqs                                         | overlap | conf |
| ----- | ------------------------------------------------------------------------------------------- | ---------------------------------------- | ---------------------- | ------ | --------- | --------- | --------------- | ----------------------------------------------- | ------- | ---- |
| SM-41 | Shared time code blank, so EnrollmentType = F (S needs a vocational attending school)       | `shared_time_code is null`               | HB p.63 [E], [CE]      | ps.njx | expr      | CMP       | Y               | none                                            | none    | H    |
| SM-42 | ReportedSharedVoc is N, never Y                                                             | `reportedsharedvoc_yn` is N (blank: E-1) | HB p.180 [E]           | ps.njx | expr      | CMP       | Y               | CONFIRM: PS default for blank (all blank today) | none    | M    |
| SM-43 | NonPublic blank (KTAF does not report parentally placed private-school students)            | `nonpublic is null`                      | HB p.109 [CE]; WB p.12 | ps.njx | expr      | CMP       | Y               | none                                            | none    | M    |
| SM-44 | InDistrictPlacement blank (a charter attending district never equals the resident district) | `indistrictplacement is null`            | HB p.119               | ps.njx | expr      | CMP       | Y               | none                                            | none    | L    |

### A.8 County-district-school (CDS) and municipal codes

| id    | rule (plain English)                                                                                          | predicate                                                                                                | state citation                                                         | host   | test form | fix owner        | source-fixable? | prereqs                                                               | overlap | conf |
| ----- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------ | --------- | ---------------- | --------------- | --------------------------------------------------------------------- | ------- | ---- |
| SM-45 | Resident county, district and school overrides present (when blank, PS falls back to the charter's own codes) | `countycoderesident`, `districtcoderesident`, `schoolcoderesident` not null                              | HB p.64-66 [E]; PS-R #20-22                                            | ps.njx | nn ×3     | CMP (SRE intake) | Y               | none                                                                  | none    | H    |
| SM-46 | All 9 CDS columns keep fixed width with leading zeros: county 2 (or ZZ), district 4, school 3                 | `regexp_contains(countycode*, r'^[0-9Z]{2}$')`; `districtcode*` `r'^\d{4}$'`; `schoolcode*` `r'^\d{3}$'` | HB p.11, 64-74 (Character 2/4/3)                                       | ps.njx | expr      | CMP              | Y               | none                                                                  | none    | M    |
| SM-47 | Resident county-district-school triple is in the CDS list (or ZZ-0000-000)                                    | concatenated key in the CDS lookup                                                                       | HB p.64-66 [E]; RR p.9                                                 | ps.njx | rel       | CMP              | Y               | LKP: CDS codes                                                        | none    | H    |
| SM-48 | Resident codes are never the charter's own (county 80; districts 7325, 1799, 7899)                            | `countycoderesident != '80' and districtcoderesident not in ('7325','1799','7899')`                      | CDS Intro ("Charter Schools ... not resident locations"); HB p.66 [AN] | ps.njx | expr      | CMP              | Y               | none (codes from cds-fix HANDOFF)                                     | none    | H    |
| SM-49 | Resident school is a regular public school (or 000)                                                           | lookup `SchoolCategory`                                                                                  | HB p.66 [AN]                                                           | ps.njx | rel       | CMP              | Y               | LKP: CDS codes                                                        | none    | M    |
| SM-50 | Resident municipal code present and 4 digits                                                                  | `regexp_contains(residentmunicipalcode, r'^\d{4}$')`                                                     | HB p.111 [E]; Compliance ("must be 4 digits")                          | ps.njx | expr      | CMP              | Y               | none                                                                  | none    | H    |
| SM-51 | Municipal code is in the NJDOE list                                                                           | rel to District Info `Municipal Code`                                                                    | HB p.111 [AN] ("or an error will occur")                               | ps.njx | rel       | CMP              | Y               | LKP: District Info                                                    | none    | H    |
| SM-52 | Municipal code agrees with the resident district                                                              | (`residentmunicipalcode`, `districtcoderesident`) pair is in District Info                               | RR p.1                                                                 | ps.njx | sing      | CMP              | Y               | LKP: District Info                                                    | none    | M    |
| SM-53 | Attending CDS = the enrolled KTAF school, unless an out-of-district placement                                 | attending triple = school crosswalk(`schoolid`) where not `is_out_of_district`                           | RR p.7 (Scenario 10); PS-R #27-29                                      | ps.njx | sing      | CMP              | Y               | LKP: KTAF school → CDS (`prefs` not ingested: hardcode district code) | none    | M    |
| SM-54 | Receiving CDS = the KTAF charter for every record, placements included                                        | receiving triple = region charter codes                                                                  | RR p.7, 11 (Scenarios 10, 21)                                          | ps.njx | sing      | CMP              | Y               | LKP: same as SM-53                                                    | none    | M    |
| SM-55 | Receiving and Attending triples are in the CDS list and not non-operational                                   | rel                                                                                                      | HB p.68-74 [E]                                                         | ps.njx | rel       | CMP              | Y               | LKP: CDS codes                                                        | none    | H    |
| SM-56 | Grade is offered at the Attending school (otherwise PTC must be 18-33 or 38)                                  | state grade code is in the CDS grade columns for the attending triple                                    | HB p.87 [CE], p.89; WB p.32                                            | ps.njx | sing      | CMP              | Y               | LKP: CDS grade columns                                                | none    | H    |

### A.9 Entry and exit dates

| id    | rule (plain English)                                                                                                           | predicate                                                                    | state citation         | host   | test form  | fix owner               | source-fixable? | prereqs     | overlap                                                               | conf |
| ----- | ------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- | ---------------------- | ------ | ---------- | ----------------------- | --------------- | ----------- | --------------------------------------------------------------------- | ---- |
| SM-57 | District entry date present (1899/1900 is PowerSchool's blank)                                                                 | `districtentrydate > '1900-01-01'`                                           | HB p.67 [E]            | ps.njx | expr       | DT (autocomm writes it) | N               | none        | none                                                                  | H    |
| SM-58 | School entry date present                                                                                                      | `schoolentrydate > '1900-01-01'` (otherwise PS falls back to `entrydate`)    | HB p.76 [E]; PS-R #31  | ps.njx | expr       | DT                      | N               | none        | none                                                                  | M    |
| SM-59 | School entry not before district entry                                                                                         | `schoolentrydate >= districtentrydate`                                       | HB p.76 [CE]           | ps.njx | expr       | DT                      | N               | none        | none                                                                  | H    |
| SM-60 | No entry date beyond the window (Fall ≤ Oct 15; EOY ≤ Jun 30)                                                                  | `greatest(districtentrydate, schoolentrydate, entrydate) <= window_end`      | HB p.67, 76 [AN], [CE] | ps.njx | expr       | REG                     | Y               | var: window | none                                                                  | M    |
| SM-61 | School entry date = first day at this school (does not reset each year; later than the district date after an in-network move) | `schoolentrydate` = first attended day of the unbroken run at `schoolid`     | HB p.76 [AN]           | ps.njx | sing       | DT                      | N               | none        | none                                                                  | L    |
| SM-62 | Inactive current-year stint has an exit code                                                                                   | `exitcode is not null` where INACT                                           | HB p.78-79 [E]         | ps.enr | nn + where | REG                     | Y               | none        | none                                                                  | H    |
| SM-63 | Active stint has no exit code                                                                                                  | `exitcode is null` where ACT                                                 | HB p.81 [CE]           | ps.enr | expr       | REG                     | Y               | none        | none                                                                  | H    |
| SM-64 | Exit after entry (no-shows: exit = first day)                                                                                  | `exitdate > entrydate`                                                       | HB p.78; WB p.13       | ps.enr | expr       | REG                     | Y               | none        | T: `int_powerschool__ps_enrollment_all` `entrydate < exitdate` (warn) | M    |
| SM-65 | June exits, graduates included, stay active until after the EOY snapshot                                                       | `exitdate >= date(academic_year + 1, 6, 1)` and inactivated before EOY close | HB p.78, 81 [W]        | ps.enr | expr       | REG                     | Y               | var: window | none                                                                  | L    |

### A.10 Entry and exit codes

| id    | rule (plain English)                                                                                           | predicate                                                           | state citation                                 | host        | test form  | fix owner | source-fixable? | prereqs                       | overlap         | conf |
| ----- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------- | ----------- | ---------- | --------- | --------------- | ----------------------------- | --------------- | ---- |
| SM-66 | Active stint has an entry code                                                                                 | `entrycode is not null` where ACT                                   | HB p.172 [E]                                   | ps.enr      | nn + where | REG       | Y               | none                          | NF blank        | H    |
| SM-67 | Entry code is E1, R1-R7 or R9-R14                                                                              | av                                                                  | HB p.171-172 [E]                               | ps.enr (CY) | av         | REG       | Y               | none                          | NF invalid code | H    |
| SM-68 | R13 means "returning to the resident district from a charter", so a charter should not receive it              | `entrycode != 'R13'`                                                | HB p.172 (definition)                          | ps.enr (CY) | expr       | REG       | Y               | none                          | NF R13          | L    |
| SM-69 | New kindergartner coded E1                                                                                     | `year_in_network = 1 and grade_level = 0` ⇒ `entrycode = 'E1'`      | KTAF SY22 mapping                              | ps.enr (CY) | expr       | REG       | Y               | LKP: entry-code mapping sheet | NF              | L    |
| SM-70 | New student (grades 1-12) is not R1/R2, and is in E1, R3, R4, R6, R12, R13                                     | `year_in_network = 1 and grade_level > 0` ⇒ code in the mapping set | KTAF SY22 mapping                              | ps.enr (CY) | expr       | REG       | Y               | LKP: entry-code mapping sheet | NF              | L    |
| SM-71 | Returning student coded R1 (same school) or R2 (another KTAF school)                                           | `year_in_network > 1` ⇒ `entrycode in ('R1','R2')`                  | HB p.171-172 (R1/R2 definitions); KTAF mapping | ps.enr (CY) | expr       | REG       | Y               | LKP: entry-code mapping sheet | NF              | M    |
| SM-72 | Exit code in the state list (T2-T4, T6-T10, TC, TR, TD, TA, TP, D1, D3-D11, L, PPE); T1, T5 and D2 are invalid | av                                                                  | HB p.79-81 [E]; p.27 (D2 removed)              | ps.enr (CY) | av         | REG       | Y               | CONFIRM: PS translation (E-3) | none            | H    |
| SM-73 | Graduates reported with L (PowerSchool stores G1)                                                              | `exitcode = 'G1'` ⇒ the extract emits L                             | HB p.79                                        | ps.enr      | sing       | CMP       | Y               | CONFIRM: PS translation       | none            | M    |
| SM-74 | Dropout codes D3-D8 only at age 16 or older                                                                    | `exitcode in ('D3'..'D8')` ⇒ `date_diff(exitdate, dob, year) >= 16` | HB p.81 [W]                                    | ps.enr      | expr       | REG       | Y               | none                          | none            | L    |

### A.11 Grade, program type, tuition, graduation year, retained

| id    | rule (plain English)                                                                                 | predicate                                                   | state citation               | host                | test form | fix owner               | source-fixable? | prereqs                           | overlap                                      | conf |
| ----- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ---------------------------- | ------------------- | --------- | ----------------------- | --------------- | --------------------------------- | -------------------------------------------- | ---- |
| SM-75 | Grade level is K-12; the `gradelevelcode` override, if set, is in the handbook list                  | `grade_level between 0 and 12` (CY); av on `gradelevelcode` | HB p.86-87 [E]               | ps.enr (CY); ps.njx | av        | REG                     | Y               | none                              | none (only a finalsite model has a grade av) | H    |
| SM-76 | PTC override in the handbook list; NE only with grade 12; never 34-37                                | av on `programtypecode` + expr                              | HB p.88-89 [E], [AN]         | ps.njx              | av + expr | CMP                     | Y               | none                              | none                                         | M    |
| SM-77 | Tuition code 07 for charter students (03 only in the first year after a non-public school); never 06 | `ltrim(tuition_code, '0') in ('7','3')`                     | HB p.82 [AN]; p.83 [CE] (06) | ps.njx              | av        | CMP                     | Y               | none                              | none                                         | M    |
| SM-78 | Year of graduation is 4 digits and = `academic_year + 13 - grade_level`                              | expr                                                        | HB p.75 [E]                  | ps.njx              | expr      | DT (autocomm writes it) | N               | CONFIRM: PS-R source column (E-8) | none                                         | M    |
| SM-79 | Retained flag is 0/1 (PS maps 1 to Y, else N)                                                        | `retained_tf in (0, 1)`                                     | HB p.90 [E]                  | ps.njx              | av        | DT                      | N               | none                              | none                                         | L    |

### A.12 Program flags (FRL, homeless, migrant, Title I, military, gifted, alternative education, learning environment, immigrant, home language)

The handbook has no Section 504 element, so there is no 504 rule to test for
this submission (E-17).

| id     | rule (plain English)                                                                            | predicate                                                                                                   | state citation           | host           | test form  | fix owner | source-fixable? | prereqs                                                       | overlap                                                             | conf |
| ------ | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------ | -------------- | ---------- | --------- | --------------- | ------------------------------------------------------------- | ------------------------------------------------------------------- | ---- |
| SM-80  | Lunch status maps to a state value; S only through `lunchstatusoverride`                        | `lunchstatus in ('F','FDC','T','R','RDC','P','E')` or null                                                  | HB p.84-85; PS-R #35     | ps.enr (CY)    | av         | OPS       | Y               | none                                                          | none (only a Miami-only nn exists)                                  | M    |
| SM-81  | PowerSchool lunch status agrees with Titan's current-year determination                         | `lunchstatus` class = `stg_titan__person_data.eligibility_name` class                                       | HB p.84-85 (definitions) | kt.seu + Titan | sing       | OPS       | Y               | CONFIRM: what autocomm `eligibility_name` writes              | none                                                                | L    |
| SM-82  | Homeless is N, Y1 or Y2, not blank                                                              | `homeless_code in ('N','Y1','Y2')` + not_null                                                               | HB p.161 [E]             | ps.njx         | nn + av    | OPS       | Y               | CONFIRM: PS-R source column and blank default                 | T: av on kipptaf `int_students__student_enrollments` (warn; a view) | H    |
| SM-83  | Homeless Y1/Y2 ⇒ nighttime residence 1-4 (0 fails)                                              | `homeless_code in ('Y1','Y2')` ⇒ `homelessprimarynighttimeres between 1 and 4`                              | HB p.160 [E]             | ps.njx         | expr       | OPS       | Y               | none                                                          | T: av [0-4] (allows 0)                                              | H    |
| SM-84  | Homeless Y1/Y2 ⇒ instructional and support service Y/N                                          | `homelessinstrucservice in ('Y','N') and homelesssupportservice in ('Y','N')`                               | HB p.163-166 [E]         | ps.njx         | expr       | OPS       | Y               | none                                                          | none                                                                | H    |
| SM-85  | Migrant status present (Y/N)                                                                    | `migrant_tf in (0, 1)` + not_null                                                                           | HB p.149 [E]             | ps.njx         | nn + av    | OPS       | Y               | CONFIRM: PS null mapping                                      | none                                                                | M    |
| SM-86  | Title I indicator present, 01-05                                                                | `titleiindicator in ('01','02','03','04','05')` + not_null                                                  | HB p.168 [E]             | ps.njx         | nn + av    | CMP       | Y               | CONFIRM: PS fallback (E-1)                                    | none                                                                | H    |
| SM-87  | Schoolwide Title I school ⇒ every student is 02                                                 | `titleiindicator` = the school's status                                                                     | HB p.168 [AN]            | ps.njx         | sing       | CMP       | Y               | LKP: KTAF school Title I status                               | none                                                                | M    |
| SM-88  | Military connected is 1-4, not blank (1 = not connected)                                        | `military_connected_indicator in (1, 2, 3, 4)` + not_null                                                   | HB p.112 [E]             | ps.njx         | nn + av    | OPS       | Y               | none                                                          | none                                                                | H    |
| SM-89  | Gifted and talented Y/N present                                                                 | `gifted_and_talented in ('Y','N')` + not_null                                                               | HB p.130 [E]             | ps.njx         | nn + av    | OPS       | Y               | CONFIRM: PS default                                           | none                                                                | H    |
| SM-90  | Alternative education program Y/N present                                                       | `alternativeeducationprogram_yn in ('Y','N')` + not_null                                                    | HB p.167 [E]             | ps.njx         | nn + av    | CMP       | Y               | CONFIRM: PS default                                           | none                                                                | H    |
| SM-91  | Student learning environment present, 1-4                                                       | `learningenvironment in (1, 2, 3, 4)` + not_null                                                            | HB p.131 [E]             | ps.njx         | nn + av    | OPS       | Y               | none                                                          | none                                                                | H    |
| SM-92  | SLE 1 ⇒ remote present and absent both 0; SLE 2-4 ⇒ not both 0 [EOY]                            | expr on calculated remote days                                                                              | HB p.131-135 [E]         | ps.njx         | expr       | OPS       | Y               | replicate PS remote-day calculation (attendance codes)        | none                                                                | H    |
| SM-93  | SLE 2-4 ⇒ internet connectivity 1-8                                                             | `learningenvironment in (2, 3, 4)` ⇒ `internetconnectivity between 1 and 8`                                 | HB p.137 [E]             | ps.njx         | expr       | OPS       | Y               | none                                                          | none                                                                | H    |
| SM-94  | Device owner 1-7 and device type 1-5 present                                                    | av + not_null on `deviceowner`, `devicetype`                                                                | HB p.138-139 [E]         | ps.njx         | nn + av    | OPS       | Y               | none                                                          | none                                                                | H    |
| SM-95  | Immigrant status blank for students born in the US or PR                                        | `USPR` ⇒ `immigrantstatus_yn is null`                                                                       | HB p.158 [CE]            | ps.njx (CUR)   | expr       | REG       | Y               | CONFIRM: whether PS blanks it                                 | none                                                                | H    |
| SM-96  | Foreign-born: immigrant status is Y or N, not 0/1                                               | `FB` ⇒ `immigrantstatus_yn in ('Y','N')`                                                                    | HB p.157 [VC]            | ps.njx (CUR)   | expr       | REG       | Y               | none                                                          | none                                                                | M    |
| SM-97  | First US school entry < 3 years before the snapshot ⇒ immigrant Y; Y ⇒ first-entry date present | `date_diff(d, firstentrydateintoausschool, year) < 3` ⇒ `immigrantstatus_yn = 'Y'`; `= 'Y'` ⇒ date not null | HB p.158-159 [CE]        | ps.njx (CUR)   | expr       | REG       | Y               | none                                                          | none                                                                | H    |
| SM-98  | Foreign-born ⇒ first US school entry date present                                               | `FB` ⇒ `firstentrydateintoausschool is not null`                                                            | HB p.159                 | ps.njx (CUR)   | expr       | REG       | Y               | none                                                          | none                                                                | M    |
| SM-99  | Home language 1 present and on the NJDOE list                                                   | `home_language` not null + rel                                                                              | HB p.154 [E], p.155 [CE] | ps.njx (CUR)   | nn + rel   | REG       | Y               | LKP: home language codes; CONFIRM: PS "eng" default parameter | none                                                                | H    |
| SM-100 | Home languages 2-5 on the list, with no repeats                                                 | rel + expr on `home_language2`..`home_language5`                                                            | HB p.154                 | ps.njx (CUR)   | rel + expr | REG       | Y               | LKP: home language codes                                      | none                                                                | M    |
| SM-101 | Health insurance provider set ⇒ status Y                                                        | `healthinsprovider is not null` ⇒ `healthinsstatus_yn = 'Y'`                                                | HB p.152-153 [E]         | ps.njx (CUR)   | expr       | OPS       | Y               | none                                                          | none                                                                | M    |

### A.13 Multilingual learners (LIEP)

| id     | rule (plain English)                                                                                 | predicate                                                                                                                         | state citation         | host   | test form | fix owner | source-fixable? | prereqs                                                                                         | overlap | conf |
| ------ | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ------ | --------- | --------- | --------------- | ----------------------------------------------------------------------------------------------- | ------- | ---- |
| SM-102 | Screener date set ⇒ EligibleForLIEP is Y or N                                                        | `elp_screener_date is not null` ⇒ `eligible_for_liep in ('Y','N')`                                                                | HB p.95 [E]            | ps.njx | expr      | CMP       | Y               | none                                                                                            | none    | H    |
| SM-103 | LIEP start date set ⇒ EligibleForLIEP not blank                                                      | `lepbegindate is not null` ⇒ `eligible_for_liep is not null`                                                                      | HB p.97 [E]            | ps.njx | expr      | CMP       | Y               | none                                                                                            | none    | H    |
| SM-104 | LIEP dates not in the future; start < end < start2 < end2                                            | `lepbegindate <= d`, `lependdate <= d`, `lepbegindate < lependdate`, `lependdate < lepbegindate2`, `lepbegindate2 < liependdate2` | HB p.97-103 [E]        | ps.njx | expr      | CMP       | Y               | none                                                                                            | none    | H    |
| SM-105 | LIEP end needs start; start2 needs start and end; end2 needs start2                                  | expr                                                                                                                              | HB p.99-104 [E]        | ps.njx | expr      | CMP       | Y               | none                                                                                            | none    | H    |
| SM-106 | LIEP start2 ⇒ EligibleForLIEP Y                                                                      | `lepbegindate2 is not null` ⇒ `eligible_for_liep = 'Y'`                                                                           | HB p.102 [CE]          | ps.njx | expr      | CMP       | Y               | none                                                                                            | none    | M    |
| SM-107 | K-12 student eligible Y ⇒ ELP screener date present                                                  | `eligible_for_liep = 'Y' and grade_level between 0 and 12` ⇒ `elp_screener_date is not null`                                      | HB p.107 [VC], [CE]    | ps.njx | expr      | CMP       | Y               | none                                                                                            | none    | M    |
| SM-108 | Active LIEP (Y, start date, no end, no refusal) ⇒ program code 1-5 or 7                              | expr                                                                                                                              | HB p.121-122 [VC]      | ps.njx | expr      | CMP       | Y               | GAP: PS-R reads `[S_NJ_STU]LanguageInstructionEducationalProgram`; no ingested column confirmed | none    | M    |
| SM-109 | Language of instruction on the 22-code list; program 1-3 ⇒ not ENG; 4-5 ⇒ ENG; 7 ⇒ the home language | av + expr on `liep_type` (PS-R) or `liep_languageofinstruction` (PS-S)                                                            | HB p.146-147 [E], [VC] | ps.njx | av + expr | CMP       | Y               | GAP: needs the SM-108 column; CONFIRM: which language column                                    | none    | M    |
| SM-110 | Parent refusal date on or after July 1 of the current year                                           | `liep_parent_refusal_date >= date(academic_year, 7, 1)`                                                                           | HB p.105 [W]           | ps.njx | expr      | CMP       | Y               | none                                                                                            | none    | L    |
| SM-111 | ML for more than 4 school years with no LIEP end date                                                | `lepbegindate < date(academic_year - 4, 7, 1) and lependdate is null`                                                             | HB p.97-98 [W]         | ps.njx | expr      | CMP       | Y               | none                                                                                            | none    | L    |

### A.14 Special education

| id     | rule (plain English)                                                                                              | predicate                                                                  | state citation        | host   | test form | fix owner                  | source-fixable? | prereqs                                          | overlap | conf |
| ------ | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | --------------------- | ------ | --------- | -------------------------- | --------------- | ------------------------------------------------ | ------- | ---- |
| SM-112 | SpEd classification is 00, 01-12, 14-17, 19 or 99 (13 and 18 retired; 12 preschool only)                          | av on `specialed_classification`                                           | HB p.91-92 [VC], [AN] | ps.njx | av        | CMP (EdPlan; DT writes PS) | Y (EdPlan)      | none                                             | none    | M    |
| SM-113 | Code 99 ⇒ declassification date                                                                                   | `specialed_classification = '99'` ⇒ `declassificationspeddate is not null` | HB p.94 [E]           | ps.njx | expr      | CMP (EdPlan) / DT          | Y               | the autocomm IEP feed does not write this column | none    | H    |
| SM-114 | Grade 12 with SpEd 01-17 [Apr-Jun], and L exits with SpEd 01-17 ⇒ IEP graduation course and attendance are 1 or 2 | expr on `iepgradcourserequirement`, `iepgraduationattendance`              | HB p.142-145 [VC]     | ps.njx | expr      | CMP                        | Y               | var: window                                      | none    | M    |

### A.15 Grade 12 and graduation

| id     | rule (plain English)                                                                                                            | predicate                                                                         | state citation         | host   | test form  | fix owner                            | source-fixable? | prereqs                                                                        | overlap                 | conf |
| ------ | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ---------------------- | ------ | ---------- | ------------------------------------ | --------------- | ------------------------------------------------------------------------------ | ----------------------- | ---- |
| SM-115 | Active grade 12: ELA and Math pathway present                                                                                   | not_null on `graduation_pathway_ela`, `graduation_pathway_math` where G12 and ACT | HB p.113, 116 [E]      | ps.njx | nn + where | DT (autocomm writes them)            | N               | none                                                                           | none                    | H    |
| SM-116 | Pathway values in S, D, E, H, I, J, K, M, N, O, P, Q, R                                                                         | av on both pathway columns                                                        | HB p.113-116           | ps.njx | av         | DT                                   | N               | none                                                                           | none (kt.gpc has no av) | H    |
| SM-117 | L exit after 2023-09-01: pathway in D, E, H, I, J, K, M, N, Q, S; O, P and R never with L                                       | expr                                                                              | HB p.114, 117 [VC]     | ps.njx | expr       | DT                                   | N               | none                                                                           | none                    | M    |
| SM-118 | Pathway M ⇒ SpEd classification not blank, 99 or 00                                                                             | expr                                                                              | HB p.114, 117 [VC]     | ps.njx | expr       | DT / CMP                             | N               | none                                                                           | none                    | M    |
| SM-119 | Pathway Q never used (it needs grade A1/A2)                                                                                     | pathway `!= 'Q'`                                                                  | HB p.114, 117 [VC]     | ps.njx | expr       | DT                                   | N               | none                                                                           | none                    | M    |
| SM-120 | From the EOY snapshot through the Grad snapshot, active grade 12 = O or P                                                       | expr                                                                              | HB p.114, 117 [VC]     | ps.njx | expr       | DT                                   | N               | var: window                                                                    | none                    | L    |
| SM-121 | FAFSA is C, E or N; present for active grade 12 [Apr-Jun] and for L exits                                                       | av + not_null where                                                               | HB p.183 [VC]          | ps.njx | nn + av    | DT (autocomm writes `s_stu_x.fafsa`) | N               | var: window                                                                    | none                    | M    |
| SM-122 | L exit after 2025-09-01 ⇒ FAFSA C or E                                                                                          | expr                                                                              | HB p.183 [VC]          | ps.njx | expr       | DT                                   | N               | none                                                                           | none                    | M    |
| SM-123 | Grade 12 with pathway O or P and no L exit ⇒ FAFSA N                                                                            | expr                                                                              | HB p.183 [VC]          | ps.njx | expr       | DT                                   | N               | none                                                                           | none                    | M    |
| SM-124 | Federal HS math testing requirement (A-G) present for active grade 12 [EOY] and for L exits                                     | not_null + av                                                                     | HB p.140 [VC], [E]     | ps.njx | nn + av    | CMP                                  | Y               | CONFIRM: PS-R column (`firsthsmathassessment_yn` or `federalhsmathtestingreq`) | none                    | M    |
| SM-125 | Grade 12: Biliterate Y/N present [after Fall through Grad]; any world-language field set ⇒ not N                                | expr on `biliterate_yn`, `worldlang_*`                                            | HB p.123-124 [E]       | ps.njx | expr       | CMP                                  | Y               | var: window                                                                    | none                    | H    |
| SM-126 | World language assessment on the handbook list; assessed language on the code list, no repeats, not eng; Latin and ASL pairings | av + rel + expr on `worldlang_assessment1..5`, `worldlang_assessed1..5`           | HB p.125-129 [E], [VC] | ps.njx | sing       | CMP                                  | Y               | LKP: world languages assessed codes                                            | none                    | M    |
| SM-127 | Biliterate Y ⇒ ELA pathway in D, E, H, I, J, K, M, N, Q, R, S                                                                   | expr                                                                              | HB p.114 [VC]          | ps.njx | expr       | DT                                   | N               | none                                                                           | none                    | M    |
| SM-128 | Grade 8: tech literacy is NE at Fall (Y/N/NE later); blank for other grades                                                     | expr on `eighthtechlit`                                                           | HB p.151 [VC]          | ps.njx | expr       | CMP                                  | Y               | var: window                                                                    | none                    | M    |

### A.16 Residence

| id     | rule (plain English)                           | predicate                                                        | state citation | host         | test form | fix owner        | source-fixable? | prereqs                                                         | overlap | conf |
| ------ | ---------------------------------------------- | ---------------------------------------------------------------- | -------------- | ------------ | --------- | ---------------- | --------------- | --------------------------------------------------------------- | ------- | ---- |
| SM-129 | City of residence present, with no punctuation | `not blank(city) and not regexp_contains(city, r"[^A-Za-z '-]")` | HB p.148 [E]   | ps.enr (CUR) | expr      | REG (SRE intake) | Y               | GAP: the `[S_NJ_STU_X]CityofResidence` override is not ingested | none    | H    |

### A.17 Attendance (cumulative fields)

| id     | rule (plain English)                                                                                          | predicate                                                                                                                                                      | state citation              | host                               | test form  | fix owner | source-fixable? | prereqs                                                | overlap                                                | conf |
| ------ | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- | ---------------------------------- | ---------- | --------- | --------------- | ------------------------------------------------------ | ------------------------------------------------------ | ---- |
| SM-130 | Every current-year stint has daily membership (otherwise PS reports 0 present and 0 absent)                   | the stint has rows in `int_powerschool__ps_adaadm_daily_ctod` with `membershipvalue = 1`                                                                       | HB p.175-178; PS-R #91-92   | ps.enr (CY)                        | sing       | OPS       | Y               | none (Paterson `attendancevalue` is unreliable, #4193) | A6 (FTEID); T: `..fteid_belongs_to_school_year` (warn) | M    |
| SM-131 | Attendance overrides, when set, are whole numbers 0-366 (DaysOpen 180-250)                                    | `daysopen between 180 and 250`; `cumulativedayspresent`, `cumulativedaysabsent`, `cumulativestateabs`, `remotedayspresent`, `remotedaysabsent` whole and 0-366 | HB p.173-179 [VC]; PS-R #90 | ps.njx                             | expr       | OPS       | Y               | none                                                   | none                                                   | M    |
| SM-132 | Remote present ≤ present; remote absent ≤ absent                                                              | expr on calculated values                                                                                                                                      | HB p.133, 135 [VC]          | ps.njx                             | expr       | OPS       | Y               | replicate PS calculation                               | none                                                   | M    |
| SM-133 | Present + absent ≤ membership days ≤ days open                                                                | sing over ADA/ADM and the calendar                                                                                                                             | HB p.173-178 [AN]           | ps.enr (CY)                        | sing       | OPS       | Y               | none                                                   | none                                                   | L    |
| SM-134 | Every attendance code used this year maps to a state category (present, absent, NJ excused, RemoteP, RemoteA) | category not null on codes in use                                                                                                                              | PS-R #60-61, #93            | `stg_powerschool__attendance_code` | nn + where | CMP       | Y               | CONFIRM: category column in staging                    | none                                                   | M    |

### Tally

| Measure                                                                          |                Count |
| -------------------------------------------------------------------------------- | -------------------: |
| Candidates                                                                       |                  134 |
| H confidence                                                                     |                   62 |
| M confidence                                                                     |                   50 |
| L confidence                                                                     |                   22 |
| Blocked on an ingestion gap (`GAP:`)                                             | 3 (SM-108, 109, 129) |
| Need a lookup table (`LKP:`): 10 on an NJDOE code list, 6 on KTAF-internal lists |                   16 |
| Overlap any existing audit check, njsleds rule or dbt test                       |                   41 |
| ...of which an existing dbt test or audit check (not njsleds only)               |                   19 |
| Not source-fixable (data-team code)                                              |                   16 |
| Host is the proposed `ps.njx` or `ps.race` (not built)                           |                  100 |

---

## B. Lookup tables the tests need

Repo rule: no dbt seeds. A "table" means a Google Sheet external source plus a
`stg_google_sheets__*` model.

| Lookup                                                                                                                                                                | NJDOE source (`doc_urls.txt` line)                                                                                              | Used by                        | Hardcode or table                              | Notes                                                                                                                                                                |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CDS codes: county, district, school, `SchoolCategory`, grade columns, `PreschoolExpansionAid`                                                                         | `County_District_School_Code_List.xlsx`, CDS Codes sheet (line 8)                                                               | SM-47, 49, 53-56               | Table (thousands of rows; republished in-year) | The site copy (2026-10-14) differs from `code-lookups/` (10/6). Add a ZZ-0000-000 row by hand (RR p.9). No school-level "non-operational" flag exists (catalog Q31). |
| District Info: municipal code, county per district, Choice District                                                                                                   | same file, District Info sheet (line 8)                                                                                         | SM-51, 52; SM-77 (06 check)    | Table (751 rows)                               | `code-lookups/district_info.csv` was derived from the older copy.                                                                                                    |
| NCES country codes                                                                                                                                                    | `Country-Codes.pdf` (line 7)                                                                                                    | SM-31                          | Table (248 codes)                              | A PDF, so it needs extraction. The TMPL-A Countries list (248, includes R) is a ready alternative.                                                                   |
| Home language codes (ISO 639-2)                                                                                                                                       | `Home-Language_Codes.xlsx` (line 10)                                                                                            | SM-99, 100; SM-109 (program 7) | Table (543)                                    |                                                                                                                                                                      |
| World languages assessed codes                                                                                                                                        | `World-Languages_Assessed-Codes.xlsx` (line 28)                                                                                 | SM-126                         | Table (564)                                    | 3-letter codes vs the handbook's names (catalog Q16)                                                                                                                 |
| State of birth codes                                                                                                                                                  | Data Handbook p.50-51 (line 58)                                                                                                 | SM-29, 30                      | Hardcode (62, stable)                          |                                                                                                                                                                      |
| School exit codes                                                                                                                                                     | HB p.79-81; `School-Exit-Withdrawal-Codes-and-Graduation-Cohort-Status-Overview-Cohort.pdf` (line 38)                           | SM-72-74                       | Hardcode (25)                                  | Add a local-to-state crosswalk table only if PowerSchool stores local codes such as G1 (E-3).                                                                        |
| School entry codes                                                                                                                                                    | HB p.171-172                                                                                                                    | SM-66-68                       | Hardcode (14)                                  |                                                                                                                                                                      |
| KTAF entry-code mapping (new vs returning)                                                                                                                            | not NJDOE: SY22 mapping Google Sheet (cds-fix HANDOFF)                                                                          | SM-69-71                       | Table (the sheet already exists)               |                                                                                                                                                                      |
| Grade levels                                                                                                                                                          | HB p.86-87                                                                                                                      | SM-56, 75                      | Hardcode (24)                                  | Plus the PS `grade_level` → state code mapping (KF, 01-12)                                                                                                           |
| Program type codes                                                                                                                                                    | HB p.88-89                                                                                                                      | SM-76                          | Hardcode (45)                                  |                                                                                                                                                                      |
| SpEd classification                                                                                                                                                   | HB p.91-92                                                                                                                      | SM-112                         | Hardcode (17)                                  |                                                                                                                                                                      |
| Graduation pathway values                                                                                                                                             | HB p.113-116                                                                                                                    | SM-116, 117, 127               | Hardcode (13)                                  | The PS help pages list outdated values (catalog Q4).                                                                                                                 |
| LIEP program codes; LIEP language of instruction                                                                                                                      | HB p.121, 146                                                                                                                   | SM-108, 109                    | Hardcode (6; 22)                               |                                                                                                                                                                      |
| World language assessment values                                                                                                                                      | HB p.126                                                                                                                        | SM-126                         | Hardcode (16)                                  | The TMPL-A list differs (NEWT, no AAPPL ASL)                                                                                                                         |
| Small enums: gender, Y/N, homeless, nighttime residence, Title I, tuition, military, SLE, device owner/type, connectivity, FAFSA, FedHSMath, IEPGrad, eighth tech lit | HB page per element                                                                                                             | many                           | Hardcode                                       |                                                                                                                                                                      |
| KTAF school → own CDS (attending/receiving), Title I status                                                                                                           | not NJDOE: `stg_powerschool__schools` (`countynbr`, `alternate_school_number`, `school_number`) plus a per-region district code | SM-53, 54, 87                  | Small table or per-region hardcode (3 regions) | `prefs` (`District_Number`) is not ingested. The district codes from cds-fix are Newark 80/7325, Camden 07/1799, Paterson 80/7899.                                   |
| Attendance code → state category                                                                                                                                      | PowerSchool `attendance_code` (ingested)                                                                                        | SM-92, 132, 134                | Existing source                                | Confirm the category column survives staging                                                                                                                         |
| Titan meal eligibility                                                                                                                                                | existing `stg_titan__person_data`                                                                                               | SM-81                          | Existing model                                 |                                                                                                                                                                      |
| Country, state and NJ county word lists                                                                                                                               | `njsleds_flags.py`                                                                                                              | SM-35                          | Hardcode in the test                           |                                                                                                                                                                      |

---

## C. Regression tests (error-level, #5558 step 3)

These are proposals. None carries ticketing `meta`.

1. **`int_students__student_enrollment_union` (kt.seu), already exists.** The
   ucc on (`student_number`, `_dbt_source_project`, `academic_year`,
   `entrydate`) at error pairs with SM-03. Add "one open stint per student per
   date" at error if kt.seu gains a covering-stint pick (pairs with SM-02).
2. **`rpt_powerschool__autocomm_students` (kt.aut)** rebuilds the logic behind
   data-team-written fields:
   - `district_entry_date` and `school_entry_date` parse, are not null, and
     school ≥ district (SM-57-59).
   - `graduation_year` is between `var('current_academic_year') + 1` and `+ 13`
     (SM-78).
   - `retained_tf in (0, 1)` (SM-79).
   - `s_stu_x__fafsa in ('C','E','N')`, and pathway O/P ⇒ N (SM-121, 123).
   - Pathway columns are av [S..R] and never Q (SM-116, 119).
3. **`int_students__graduation_path_codes` (kt.gpc):** `final_grad_path_code` av
   at error (SM-116); M only when a SpEd code is present (SM-118).
4. **`rpt_powerschool__autocomm_students_iep`:**
   `s_nj_stu_x__specialed_classification` av [00, 01-12, 14-17, 19, 99] at error
   (SM-112). If the feed can write 99, it must also write a declassification
   date; it does not today (SM-113).
5. **`int_powerschool__district_entry_date`**, the defended source for SM-57/59:
   unique `studentid` where `rn_entry = 1` at error, if no such test exists.
6. **Conformed demographics (`dim_students` or
   `int_students__student_enrollments`).**
   - Proposed defense: out-of-domain values (`fedethnicity = -1`, blank or other
     gender, non-Hispanic with no race) land in an explicit unknown bucket, not
     silently in "N" or "Not Hispanic".
   - Regression: not_null + av at error on the decoded columns (pairs with
     SM-23, 36, 37).
7. **Any conformed CDS, municipal or country code column the data team
   publishes.** Defense: `lpad` in the conformed model. Regression: a
   fixed-width regex at error (pairs with SM-33, 46, 50).
8. **Only if the data team builds a dbt state-file preview** (the "No waivers"
   path for correct-but-rejected names): a character-class and length test at
   error on that model's output (pairs with SM-14-17).

---

## D. Rules we cannot test from PowerSchool alone

| Rule                                                                                          | Needs                                                             | Export columns                                                                             |
| --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| SID exists as an issued SID, beyond 10-digit format (HB p.42)                                 | NJSLEDS Student Snapshot Records or ID Master export              | `StateIdentificationNumber`, `LocalIdentificationNumber`, record status                    |
| SID-to-demographics match: the key identity fields the ID Master overwrites (UNR p.1)         | ID Master export per SID                                          | `FirstName`, `MiddleName`, `LastName`, `DateOfBirth`, `Gender`                             |
| Duplicate SID active in another LEA; pending transfer requests (HB p.42; WB p.8)              | Transfer request list / cross-LEA status                          | SID, Associated vs Requesting district, `DistrictStatus`, `SchoolStatus`, `EnrollmentType` |
| Records stuck as Unresolved, Associated SID or New SID that need re-upload (SID p.1; UNR p.2) | Upload record status export                                       | SID, LID, record status (Error / Sync / Unresolved / Transfer; Associated / New)           |
| Calibrate this catalog against actual rejections                                              | NJSLEDS Error Report ("Record Level", "Error By Type")            | LID, SID, element, error message, warning flag                                             |
| Migrant, Immigrant and Homeless changed since the Fall snapshot [W] (HB p.150, 157, 162)      | Fall Snapshot export                                              | SID, `MigrantStatus`, `ImmigrantStatus`, `Homeless`                                        |
| A record captured in a snapshot later disappears (WB p.17)                                    | Fall Snapshot record list                                         | SID, LID, Attending CDS, `SchoolEntryDate`, `SchoolStatus`                                 |
| Grades registered in NJDOE Homeroom differ from the published CDS file (WB p.32)              | Homeroom / CDS registration export                                | county, district, school, grades offered                                                   |
| SpEd 00 and 99 timing relative to the last snapshot (HB p.92-93)                              | Prior snapshot export plus the "Date Report Last Submitted" input | SID, `SpecialEducationClassification`, snapshot date                                       |
| Grad and Biliteracy snapshot contents (HB p.114)                                              | Graduation and Biliteracy snapshot exports                        | SID, pathways, `SchoolExitWithdrawalCode`, `FAFSACompletionIndicator`, `Biliterate`        |
| What PowerSchool emits for blanks, fallbacks and local codes (E-1, E-3)                       | Not the portal: the PS-generated SM CSV from each run, saved      | all 104 template columns                                                                   |

---

## E. Open questions for the morning review

The first 3 matter most.

1. **What does the PowerSchool SM report emit for blank fields?**
   - These fields are mostly blank in PowerSchool: Title I, gifted, alternative
     education, homeless, home language, military, ReportedSharedVoc, eighth
     tech literacy, and the IncludeInNJSMART flag.
   - Either PowerSchool defaults them on output or they reject. That decides
     whether 11 rows (SM-32, 42, 82, 85, 86, 88-90, 95, 99, 128), 7 of them H,
     are real or noise.
   - To resolve: pull the last generated file and the NJSLEDS Error Report
     (Section D).
2. **How #5558 fits a file built outside dbt.**
   - (a) PowerSchool builds the SM file, so there is no dbt state-file model to
     "defend downstream". Step 2 has a home only for warehouse consumers
     (Section C).
   - (b) 16 rules cover fields the data team writes into PowerSchool (entry
     dates, graduation year, retained, pathways, FAFSA, SpEd). Those are code
     fixes with error tests, not tickets.
   - (c) NJSLEDS refuses prior-year uploads (PS-R), and `s_nj_stu_x` keeps only
     current values. Proposal: scope SM tests to CY, with CUR for student-level
     fields. That departs from #5558's "every record ever covered". Who rules?
3. **Local code sets vs state code sets.**
   - PowerSchool history holds exit codes G1, T1, PR, TO, RE, TS and D2, and
     entry codes P, OE, R, RT. Graduates are G1, not L.
   - `immigrantstatus_yn` mixes Y/N and 0/1. `tuition_code` is '7', not '07'.
   - Does the PS extract translate these on output? That decides whether SM-67,
     72, 73 and 96 test the PowerSchool value or a mapped value.

4. **Host model.** Approve a new package int (`ps.njx`)? The alternative is
   widening kipptaf `int_students__student_enrollments`, which today is a view
   (tests would go dormant) and carries about 20 of the roughly 60 needed `s_nj`
   columns.
5. **Report date and windows.** Which `d` and window do windowed rules use
   (SM-60, 65, 114, 120, 121, 124, 125, 128)? Proposal: one `njsleds_window`
   variable (Fall / EOY / Grad).
6. **Population.** PS-R lists `IncludeInNJSMART_TF = Yes`, but the flag is blank
   for about 99.6% of enrolled students. `ps.enr` also drops no-shows, which the
   state wants reported (WB p.13). What report settings does Compliance run?
7. **SchoolEntryDate.** Autocomm writes SchoolEntryDate equal to
   DistrictEntryDate for every enrolled student. HB p.76 defines it per school,
   so it is wrong after a move between KTAF schools. Is that intended?
8. **YearOfGraduation source.** PS-R cites `[Students]graduation_year`.
   `studentcorefields.graduation_year` and `students.sched_yearofgraduation`
   disagree for about 63% of enrolled students. Which does the report read, and
   which does autocomm write?
9. **R13.** The KTAF mapping uses R13 for charter-to-charter arrivals (about 320
   current-year stints). HB p.172 defines R13 as a return to the resident
   district from a charter. It is a valid code, so it will not reject, but it is
   likely misreported. This is a Compliance call.
10. **Accents in names.** The handbook is silent on accented letters. Under "No
    waivers", a correct accented legal name would be cleaned in a state-file
    model, but no dbt state-file model exists. Who cleans it, and where?
11. **Fix owner for intake-fed fields** (names, DOB, birthplace, race, residence
    and CDS codes). Should record-level tickets go to the school registrar and
    the root cause to SRE-enrollment? Example: the Finalsite integration writes
    race only for single-race, non-Hispanic students.
12. **Title I.** Are all KTAF NJ schools schoolwide Title I (so every student is
    02)? About 130 enrolled students carry 01.
13. **Tuition code.** Is 07 required for every charter student? About 30
    enrolled students are blank, and the handbook says "leave blank if not
    applicable".
14. **Resident-code fallback.** Confirm that PowerSchool substitutes the
    charter's own codes when the resident overrides are blank (PS-R #20-22).
    That is what makes SM-45 and SM-48 H.
15. **Handbook contradictions that change predicates:**
    - ELPScreenerDate (catalog Q5; SM-107)
    - the FAFSA C/E date, 2024 vs 2025 (Q2; SM-122)
    - LIEPStartDate2 "blank or N" (Q20; SM-106)
    - "Status" is undefined (Q8)
    - FederalHSMath has an unconditional blank check (Q9; SM-124)
    - whether a hyphen or apostrophe counts as "punctuation" in city of birth
      (SM-34)
16. **Preschool.** Does any KTAF NJ school report PK (`grade_level < 0`)? If so,
    the DeafHardOfHearing, LanguageAcquisition, preschool-referral exemptions
    and preschool DaysOpen rules need rows; none are drafted here.
17. **Section 504.** There is no SM element for it. Confirm nothing is expected
    for this submission.
18. **Leading zeros.** CDS widths are correct today. Keep SM-46 as a guard?
    Compliance's open question still stands: does NJSLEDS reject the short form?
19. **Severity placement.** `ps.stu`-hosted ticketed tests at warn conflict with
    the rule that staging tests are `severity: error`. The precedent is the
    `stg_powerschool__cc` Ops worklist. Accept that precedent for SM-01, 05 and
    11?
20. **Paterson attendance.** Paterson `attendancevalue` is unreliable (#4193),
    so SM-130 and SM-133 will be noisy there until that is fixed.
