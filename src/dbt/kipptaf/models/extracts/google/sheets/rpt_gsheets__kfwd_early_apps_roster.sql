with
    criteria_text as (
        select
            _dbt_source_project,
            overgrad_student_id,
            criterion_code,
            is_met,
            is_near_miss,

            if(is_met, 'Yes', 'No') as status_text,
            if(is_met, qualifying_colleges, null) as colleges_when_met,
        from {{ ref("int_students__early_application_criteria_scaffold") }}
    ),

    criteria_pivot as (
        select
            _dbt_source_project,
            overgrad_student_id,

            logical_and(is_met) as is_met_all,
            countif(is_near_miss) as near_miss_count,

            max(
                if(criterion_code = 'ed_80_full_need', status_text, null)
            ) as ed_80_full_need_status,
            max(
                if(criterion_code = 'ed_80_full_need', colleges_when_met, null)
            ) as ed_80_full_need_colleges,
            max(if(criterion_code = 'ea_78', status_text, null)) as ea_78_status,
            max(
                if(criterion_code = 'ea_78', colleges_when_met, null)
            ) as ea_78_colleges,
            max(
                if(criterion_code = 'early_80_full_need', status_text, null)
            ) as early_80_full_need_status,
            max(
                if(criterion_code = 'early_80_full_need', colleges_when_met, null)
            ) as early_80_full_need_colleges,
            max(
                if(criterion_code = 'additional_68', status_text, null)
            ) as additional_68_status,
            max(
                if(criterion_code = 'additional_68', colleges_when_met, null)
            ) as additional_68_colleges,
            max(if(criterion_code = 'early_68', status_text, null)) as early_68_status,
            max(
                if(criterion_code = 'early_68', colleges_when_met, null)
            ) as early_68_colleges,
        from criteria_text
        group by _dbt_source_project, overgrad_student_id
    )

select
    r._dbt_source_project,
    r.overgrad_student_id,
    r.student_name,
    r.high_school,
    r.counselor_name,
    r.unweighted_gpa,
    r.gpa_band,
    r.submitted_early_count,
    r.submitted_early_applications,

    cp.ed_80_full_need_colleges,
    cp.ea_78_colleges,
    cp.early_80_full_need_colleges,
    cp.additional_68_colleges,
    cp.early_68_colleges,

    coalesce(cp.ed_80_full_need_status, 'N/A') as ed_80_full_need_status,
    coalesce(cp.ea_78_status, 'N/A') as ea_78_status,
    coalesce(cp.early_80_full_need_status, 'N/A') as early_80_full_need_status,
    coalesce(cp.additional_68_status, 'N/A') as additional_68_status,
    coalesce(cp.early_68_status, 'N/A') as early_68_status,
    coalesce(cp.near_miss_count, 0) as near_miss_count,

    case
        when cp.overgrad_student_id is null
        then 'N/A'
        when cp.is_met_all
        then 'Yes'
        else 'No'
    end as met_all_for_band,
from {{ ref("int_students__early_applications_rollup") }} as r
left join
    criteria_pivot as cp
    on r.overgrad_student_id = cp.overgrad_student_id
    and r._dbt_source_project = cp._dbt_source_project
where r.is_ed_ea_flagged
