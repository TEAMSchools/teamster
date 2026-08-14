with
    -- live Focus enrollments, keys pre-formatted to the export string shapes so
    -- the joins below compare plain columns (no one-sided casts in ON)
    focus_enrollment as (
        select syear, cast(student_id as string) as student_id,
        from {{ ref("stg_focus__student_enrollment") }}
    ),

    -- entry-existence key. Match on (student_id, syear) only: ops manually edit
    -- the floored start_date in Focus after import, so a start_date match would
    -- re-open an already-loaded student-year as "new".
    focus_year as (select distinct student_id, syear, from focus_enrollment),

    -- desired state from kipptaf, scoped to the current academic year.
    -- Withdrawals are excluded outright (#4769 decision I): the feed creates
    -- enrollments only, so a row carrying an end_date has nothing to add and
    -- would otherwise import as an ACTIVE enrollment with no end date once the
    -- end_date column itself is dropped from the output.
    desired as (
        select d.*,
        from {{ source("kipptaf_extracts", "rpt_focus__student_enrollment") }} as d
        where d.syear = {{ var("current_academic_year") }} and d.end_date is null
    ),

    -- entry branch: student-year absent from Focus -> send the entry row
    entries as (
        select d.*,
        from desired as d
        left join
            focus_year as fy on d.student_id = fy.student_id and d.syear = fy.syear
        where fy.student_id is null
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    syear,
    school_id,
    student_id,
    grade_id,
    start_date,
    enrollment_code,
    calendar_id,
    prior_dist,
    prior_state,
    prior_country,
    ed_choice,
    stdt_dis_affect,
    offender_transfer_stdt,
    came_from,
    moved_to,
    sec_sch,
    grde_prom_st,
    good_cause_exempt,
    graduation_requirement_program,
    next_school,
    next_grade,
    district_ood,
    sch_ood,
    include_in_class_rank,
    fl_days_present,
    fl_days_absent,
from entries
