-- Tiered Crosswalk Match + Tier C/D Corroboration
--
-- Self-scoping by academic_year = enrollment_school_year (each gap's own
-- year) - no manual parameter needed, works unchanged every year.
--
-- Tiers:
--   A/B - exact DOB + last_name (raw, or diacritic-stripped on both sides)
--   C   - exact DOB + shared last_name TOKEN (split on hyphen/space) -
--         handles compound/hyphenated surnames recorded inconsistently
--         between CB and PowerSchool (e.g. CB single-word surname vs. PS
--         surname with a name-suffix appended, or a two-word surname where
--         one side kept only one half, or a hyphen on one side vs. a space
--         on the other)
--   D   - DOB exactly 365/366 days apart (same month/day, year off by one,
--         leap-year safe) AND both first_name and last_name match exactly -
--         handles a DOB-year transcription mismatch. Requires both names
--         (not just last name) since loosening DOB raises collision risk
--         more than Tier C does.
--   Tiebreak - when Tiers A-D together yield >1 distinct student_number for
--         a gap, narrow using first_name (case-fold/diacritic-strip, plus
--         stripping non-alphanumeric characters so an apostrophe in a name
--         doesn't block the match).
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
