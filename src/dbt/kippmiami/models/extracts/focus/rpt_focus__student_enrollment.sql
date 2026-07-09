with
    decoded as (
        select d.*, dc.short_name as drop_code_decoded,
        from {{ source("kipptaf_extracts", "rpt_focus__student_enrollment") }} as d
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as dc
            on d.drop_code = dc.title
            and dc.type = 'Drop'
    ),

    -- pre-format the Focus join keys to the export string shapes so the join
    -- below compares plain columns (no one-sided casts in the ON clause).
    focus_enrollment as (
        select
            enrollment_code,
            drop_code,
            cast(student_id as string) as student_id,
            format_date('%Y%m%d', start_date) as start_date,
            format_date('%Y%m%d', end_date) as end_date,
        from {{ ref("stg_focus__student_enrollment") }}
    ),

    matched as (
        select
            e.*,
            fe.enrollment_code as focus_enrollment_code,
            fe.drop_code as focus_drop_code,
            fe.end_date as focus_end_date,
        from decoded as e
        left join
            focus_enrollment as fe
            on e.student_id = fe.student_id
            and e.start_date = fe.start_date
        where
            -- import once: keep a row only when the enrollment is new to Focus,
            -- or when Focus has no withdrawal yet and this export carries one (a
            -- one-time withdrawal fill). Existing Focus values are never
            -- overwritten — enrollment ops harmonize later changes manually.
            fe.student_id is null or (fe.end_date is null and e.end_date is not null)
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    syear,
    school_id,
    student_id,
    grade_id,
    start_date,
    if(
        focus_enrollment_code is null, enrollment_code, cast(null as string)
    ) as enrollment_code,
    if(focus_end_date is null, end_date, cast(null as string)) as end_date,
    if(focus_drop_code is null, drop_code_decoded, cast(null as string)) as drop_code,
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
from matched
