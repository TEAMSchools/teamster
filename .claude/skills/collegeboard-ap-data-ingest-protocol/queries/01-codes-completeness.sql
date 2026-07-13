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
