with
    decoded as (
        select d.*, dc.short_name as drop_code_decoded,
        from {{ source("kipptaf_extracts", "rpt_focus__student_enrollment") }} as d
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as dc
            on d.drop_code = dc.title
            and dc.type = 'Drop'
    ),

    -- pre-format the Focus join keys to the export string shapes, and translate
    -- Focus's stored numeric drop_code id back to its short code (Focus stores
    -- drop_code as an enrollment-code-table id, not the import code) so the diff
    -- compares like-for-like. enrollment_code stays the raw id — it is only
    -- null-checked for the import-once guard, never compared by value.
    focus_enrollment as (
        select
            fe.enrollment_code,

            dc.short_name as drop_code,

            cast(fe.student_id as string) as student_id,
            format_date('%Y%m%d', fe.start_date) as start_date,
            format_date('%Y%m%d', fe.end_date) as end_date,
        from {{ ref("stg_focus__student_enrollment") }} as fe
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as dc
            on fe.drop_code = dc.id
    ),

    matched as (
        select
            e.*,
            fe.enrollment_code as focus_enrollment_code,
            fe.drop_code as focus_drop_code,
        from decoded as e
        left join
            focus_enrollment as fe
            on e.student_id = fe.student_id
            and e.start_date = fe.start_date
        where
            -- keep a row when it is new to Focus, its end_date changed, or its
            -- drop_code differs from Focus (drop_code updates on change;
            -- enrollment_code is import-once, so a code-only change to it never
            -- re-emits a row).
            fe.student_id is null
            or (e.end_date is not null and e.end_date is distinct from fe.end_date)
            or e.drop_code_decoded is distinct from fe.drop_code
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
    end_date,
    if(
        drop_code_decoded is distinct from focus_drop_code,
        drop_code_decoded,
        cast(null as string)
    ) as drop_code,
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
