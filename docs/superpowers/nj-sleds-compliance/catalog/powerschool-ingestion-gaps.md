# PowerSchool fields the NJ specs read vs. what each region ingests

Generated 2026-10-20 from `[Table]Field` references in the PowerSchool NJ spec
pages (SID Management, Student Course Roster, Staff Course Roster, State
Assessment Registration, SID Information, District/School/Staff Setup) against
`INFORMATION_SCHEMA.COLUMNS` of
`dagster_kipp{newark,camden,paterson}_dlt_powerschool`. A field is present when
the raw dlt table carries the column; the dbt staging contract may still omit it
(check separately before relying on it).

## 0. Interpretation (hand-written after the generated sections)

Real gaps, same in all three regions (section 3 found zero column-set
differences across Newark, Camden and Paterson on the tables that are ingested):

- `s_nj_usr_x` — staff NJ extension: SMID (`staffmemberid`), `smart_*`
  demographics and employment fields, `excl_frm_smart_stf_submissn`. Not in any
  region's dlt table list. A `stg_powerschool__s_nj_usr_x` relation exists in
  `kippnewark_powerschool` (1,843 rows) and `kippcamden_powerschool` (1,214
  rows), both last modified 2025-08-22 (the pre-dlt method), and not at all in
  `kipppaterson_powerschool`. Every Staff Course Roster test that needs a SMID
  waits on adding this table to the dlt config in all three regions.
- `s_nj_sec_x` — section-level NJ overrides (CDS assigned codes, SCED subject
  area and course id, course level, span, sequence, type) and the section-level
  "exclude from course roster" flag. The extract reads these first and falls
  back to `s_nj_crs_x`; without them a section-level override or exclusion is
  invisible to any test.
- `s_nj_ssf_x` — per-school staff "Exclude from Course Roster Reports" flag and
  the SAR's staff-member assignment.
- `s_nj_sgr_x` — `Section_Start_Date` / `Section_End_Date` on stored grades; the
  Student Course Roster takes section entry/exit dates from here before falling
  back to `cc`.
- `s_nj_sch_x`, `prefs`, `s_nj_credentials_s`, `s_nj_final_grade_mapping_s`,
  `s_nj_bsd_period_mapping_c`, `nj_section_teacher_tracking`,
  `nj_teacher_role_mapping`, `codeset` / `code_entity`, `period`,
  `section_meeting` — setup and mapping tables. Low volume; whether to ingest
  them or treat their values as fixed configuration is a design question.

Section 2's "missing" rows are mostly spec-naming artifacts, not gaps: the specs
write `[Students]Graduation_Year` where the raw column is
`sched_yearofgraduation`, `[Schools]CountyNumber` for `countynbr`,
`[Sections]SectionID` for `id`, `[Calendar_Day]Date` for `date_value`, and
several `s_nj_stu_x` names are truncated at a slash or space in the page text
(`deaf`, `homeless`, `liep`, `special`, `gifted`). Treat each remaining row as
"confirm the raw column name" rather than "add ingestion". Column-level
confirmation against the dbt staging contracts (which may drop raw columns) is
still to do for `students`, `schools`, `sections`.

## 1. Tables the specs read

| Table                       | Spec fields cited | Newark           | Camden           | Paterson         | Note                             |
| --------------------------- | ----------------: | ---------------- | ---------------- | ---------------- | -------------------------------- |
| s_nj_stu_x                  |               179 | yes              | yes              | yes              |                                  |
| s_nj_usr_x                  |                39 | **no**           | **no**           | **no**           |                                  |
| s_nj_ren_x                  |                34 | yes              | yes              | yes              |                                  |
| students                    |                26 | yes              | yes              | yes              |                                  |
| s_nj_crs_x                  |                17 | yes              | yes              | yes              |                                  |
| schools                     |                17 | yes              | yes              | yes              |                                  |
| s_nj_sec_x                  |                13 | **no**           | **no**           | **no**           |                                  |
| gen                         |                 9 | yes              | yes              | yes              |                                  |
| attendance_code             |                 8 | yes              | yes              | yes              |                                  |
| calendar_day                |                 8 | yes              | yes              | yes              |                                  |
| sections                    |                 8 | yes              | yes              | yes              |                                  |
| codeset                     |                 7 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| s_nj_credentials_s          |                 6 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| studentcorefields           |                 6 | yes              | yes              | yes              |                                  |
| courses                     |                 5 | yes              | yes              | yes              |                                  |
| users                       |                 5 | yes              | yes              | yes              |                                  |
| code_entity                 |                 4 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| nj_teacher_role_mapping     |                 4 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| reenrollments               |                 4 | yes              | yes              | yes              |                                  |
| s_nj_final_grade_mapping_s  |                 4 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| terms                       |                 4 | yes              | yes              | yes              |                                  |
| attendance_conversion_items |                 3 | yes              | yes              | yes              |                                  |
| bell_schedule               |                 3 | yes              | yes              | yes              |                                  |
| cycle_day                   |                 3 | yes              | yes              | yes              |                                  |
| fte                         |                 3 | yes              | yes              | yes              |                                  |
| period                      |                 3 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| prefs                       |                 3 | **no**           | **no**           | **no**           |                                  |
| s_nj_bsd_period_mapping_c   |                 3 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| cc                          |                 2 | yes              | yes              | yes              |                                  |
| fee_type                    |                 2 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| nj_section_teacher_tracking |                 2 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| s_nj_sch_x                  |                 2 | **no**           | **no**           | **no**           |                                  |
| s_nj_sgr_x                  |                 2 | **no**           | **no**           | **no**           |                                  |
| s_nj_ssf_x                  |                 2 | **no**           | **no**           | **no**           |                                  |
| s_stu_x                     |                 2 | yes              | yes              | yes              |                                  |
| storedgrades                |                 2 | yes              | yes              | yes              |                                  |
| attendance_conversion       |                 1 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| department                  |                 1 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| section_meeting             |                 1 | **not ingested** | **not ingested** | **not ingested** | not in any region dlt table list |
| sectionteacher              |                 1 | yes              | yes              | yes              |                                  |
| studentrace                 |                 1 | yes              | yes              | yes              |                                  |
| userscorefields             |                 1 | yes              | yes              | yes              |                                  |

## 2. Cited fields missing from an ingested table, per region

Only tables present in at least one region. A field missing in every region may
be a spec typo, a PowerSchool virtual or override field, or a column dlt does
not pull.

| Table             | Field                        | Newark      | Camden      | Paterson    | Cited on                                               |
| ----------------- | ---------------------------- | ----------- | ----------- | ----------- | ------------------------------------------------------ |
| calendar_day      | date                         | **missing** | **missing** | **missing** | district-setup, school-setup                           |
| courses           | alt_course_number            | **missing** | **missing** | **missing** | district-setup                                         |
| s_nj_ren_x        | deafhardofhearing            | **missing** | **missing** | **missing** | smart-sid-management                                   |
| s_nj_ren_x        | homeless                     | **missing** | **missing** | **missing** | smart-sid-management                                   |
| s_nj_ren_x        | liep                         | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_ren_x        | reportedsharedvoc            | **missing** | **missing** | **missing** | smart-sid-information, smart-sid-management            |
| s_nj_stu_x        | activemilitaryconnected      | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | biliterate                   | **missing** | **missing** | **missing** | smart-sid-management                                   |
| s_nj_stu_x        | bridgeyear                   | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | cityofresidence              | **missing** | **missing** | **missing** | smart-sid-management                                   |
| s_nj_stu_x        | dayspresent                  | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | deaf                         | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | deafhardofhearing            | **missing** | **missing** | **missing** | smart-sid-management                                   |
| s_nj_stu_x        | determined                   | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | districtentrydate            | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | family_care_relase_yn        | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | gifted                       | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | homeless                     | **missing** | **missing** | **missing** | smart-sid-management                                   |
| s_nj_stu_x        | homelessinstructionalservice | **missing** | **missing** | **missing** | smart-sid-information, smart-sid-management            |
| s_nj_stu_x        | liep                         | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | liepbegindate2               | **missing** | **missing** | **missing** | smart-sid-information, smart-sid-management            |
| s_nj_stu_x        | liependdate                  | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | liepstartdate                | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | parttimestudentindicator     | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | percentagefor                | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | ptc                          | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | reportedsharedvoc            | **missing** | **missing** | **missing** | smart-sid-information, smart-sid-management            |
| s_nj_stu_x        | special                      | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_nj_stu_x        | studentlearningenvironment   | **missing** | **missing** | **missing** | smart-sid-information                                  |
| s_stu_x           | fasfa                        | **missing** | **missing** | **missing** | smart-sid-information                                  |
| schools           | alternate_state_sch_number   | **missing** | **missing** | **missing** | district-setup                                         |
| schools           | countynumber                 | **missing** | **missing** | **missing** | sleds-student-course-roster                            |
| schools           | school_name                  | **missing** | **missing** | **missing** | district-setup                                         |
| sections          | sectionid                    | **missing** | **missing** | **missing** | sleds-student-course-roster, smart-staff-course-roster |
| studentcorefields | pscore_preferred_last_name   | **missing** | **missing** | **missing** | sleds-student-course-roster                            |
| students          | graduation_year              | **missing** | **missing** | **missing** | smart-sid-information, smart-sid-management            |
| students          | homeless_code                | **missing** | **missing** | **missing** | smart-sid-information, state-assessment-registration   |
| students          | lunch_status                 | **missing** | **missing** | **missing** | state-assessment-registration                          |
| students          | nj_gradelevelcode            | **missing** | **missing** | **missing** | smart-sid-information                                  |
| students          | preferred_name               | **missing** | **missing** | **missing** | sleds-student-course-roster                            |
| students          | preferredname                | **missing** | **missing** | **missing** | sleds-student-course-roster                            |
| students          | school_entry_code            | **missing** | **missing** | **missing** | smart-sid-information                                  |
| students          | shared_time_code             | **missing** | **missing** | **missing** | smart-sid-information                                  |

Missing-field counts: kippnewark 43, kippcamden 43, kipppaterson 43

## 3. Column-set differences across regions (ingested tables only)

| Table | Only in some regions |
| ----- | -------------------- |
