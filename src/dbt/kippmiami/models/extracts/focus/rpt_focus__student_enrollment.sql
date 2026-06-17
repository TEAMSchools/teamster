with
    enrollment as (
        select
            c.finalsite_enrollment_id,
            (
                select av.value.string_value,
                from unnest(c.id_attributes) as av
                where av.field_name = '{{ var("finalsite_focus_student_id_field") }}'
                order by av.field_id
                limit 1
            ) as stdt_id,
            l.school_year_start,
            l.assigned_school,
            l.grade_canonical_name,
            l.lifecycle_action,
            l.enrollment_start_date,
            l.enrollment_end_date,
            l.withdrawal_reason,
        from {{ ref("stg_finalsite__contacts") }} as c
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on c.finalsite_enrollment_id = l.finalsite_enrollment_id
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    e.school_year_start as syear,
    sch.focus_school_id as school_id,
    e.stdt_id as student_id,
    gr.focus_grade_id as grade_id,
    format_date('%Y%m%d', e.enrollment_start_date) as start_date,
    ec.focus_enrollment_code as enrollment_code,
    if(
        e.lifecycle_action = 'transfer_out',
        format_date('%Y%m%d', e.enrollment_end_date),
        cast(null as string)
    ) as end_date,
    if(
        e.lifecycle_action = 'transfer_out', dc.focus_drop_code, cast(null as string)
    ) as drop_code,
    cast(null as string) as calendar_id,
    cast(null as string) as prior_dist,
    cast(null as string) as prior_state,
    cast(null as string) as prior_country,
    cast(null as string) as ed_choice,
    cast(null as string) as stdt_dis_affect,
    cast(null as string) as offender_transfer_stdt,
    cast(null as string) as came_from,
    cast(null as string) as moved_to,
    cast(null as string) as sec_sch,
    cast(null as string) as grde_prom_st,
    cast(null as string) as good_cause_exempt,
    cast(null as string) as graduation_requirement_program,
    cast(null as string) as next_school,
    cast(null as string) as next_grade,
    cast(null as string) as district_ood,
    cast(null as string) as sch_ood,
    cast(null as string) as include_in_class_rank,
    cast(null as int64) as fl_days_present,
    cast(null as int64) as fl_days_absent,
    cast(null as int64) as fl_days_absent_not_disc,
from enrollment as e
left join
    {{
        source(
            "kipptaf_google_sheets",
            "stg_google_sheets__focus__grade_crosswalk",
        )
    }} as gr on e.grade_canonical_name = gr.finalsite_grade_canonical_name
left join
    {{
        source(
            "kipptaf_google_sheets",
            "stg_google_sheets__focus__school_crosswalk",
        )
    }} as sch on e.assigned_school = sch.finalsite_assigned_school
left join
    {{
        source(
            "kipptaf_google_sheets",
            "stg_google_sheets__focus__enrollment_code_crosswalk",
        )
    }} as ec on e.lifecycle_action = ec.finalsite_lifecycle_action
left join
    {{
        source(
            "kipptaf_google_sheets",
            "stg_google_sheets__focus__drop_code_crosswalk",
        )
    }} as dc on e.withdrawal_reason = dc.finalsite_withdrawal_reason
