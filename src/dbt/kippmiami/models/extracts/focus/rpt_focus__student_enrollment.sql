with
    -- live Focus enrollments, keys pre-formatted to the export string shapes so
    -- the joins below compare plain columns (no one-sided casts in ON)
    focus_enrollment as (
        select
            syear,
            cast(student_id as string) as student_id,
            format_date('%Y%m%d', start_date) as start_date,
            end_date,
            drop_code,
        from {{ ref("stg_focus__student_enrollment") }}
    ),

    -- entry-existence key. Match on (student_id, syear) only: ops manually edit
    -- the floored start_date in Focus after import, so a start_date match would
    -- re-open an already-loaded student-year as "new".
    focus_year as (select distinct student_id, syear, from focus_enrollment),

    -- exit target: the student-year's open (end_date is null) Focus row and
    -- whether it already carries a drop_code. A withdrawal attaches here, keyed
    -- to the open row's actual (possibly drifted) start_date. At most one open
    -- row per (student_id, syear) is expected — enforced by a data test on
    -- stg_focus__student_enrollment.
    focus_open as (
        select
            syear,
            student_id,
            min(start_date) as start_date,
            logical_or(drop_code is not null) as has_drop_code,
        from focus_enrollment
        where end_date is null
        group by syear, student_id
    ),

    -- desired state from kipptaf with the raw drop_code label decoded to the
    -- Focus short_name
    desired as (
        select d.*, dc.short_name as drop_code_decoded,
        from {{ source("kipptaf_extracts", "rpt_focus__student_enrollment") }} as d
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as dc
            on d.drop_code = dc.title
            and dc.type = 'Drop'
    ),

    -- entry branch: student-year absent from Focus -> send the full entry row
    -- (with a same-run exit filled in if the desired row already carries one)
    entries as (
        select d.*,
        from desired as d
        left join
            focus_year as fy on d.student_id = fy.student_id and d.syear = fy.syear
        where fy.student_id is null
    ),

    -- exit branch: student-year present, its open row lacks a drop_code, and
    -- Finalsite now shows a withdrawal -> send the drop keyed to the open row's
    -- start_date; enrollment_code stays null so the entry is never overwritten
    exits as (
        select d.*, fo.start_date as focus_open_start_date,
        from desired as d
        inner join
            focus_open as fo on d.student_id = fo.student_id and d.syear = fo.syear
        where d.end_date is not null and not fo.has_drop_code
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    syear,
    school_id,
    student_id,
    grade_id,
    start_date,
    enrollment_code,
    end_date,
    drop_code_decoded as drop_code,
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

union all

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    syear,
    school_id,
    student_id,
    grade_id,
    focus_open_start_date as start_date,
    cast(null as string) as enrollment_code,
    end_date,
    drop_code_decoded as drop_code,
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
from exits
