with
    sectioned as (
        select
            _dbt_source_project,
            overgrad_student_id,
            student_name,
            high_school,
            counselor_name,
            gpa_band,
            will_apply_early_applications,
            earliest_will_apply_due_date,
            submitted_early_applications,
            submitted_no_deadline_type_applications,

            case
                when is_ed_ea_flagged and submitted_early_count = 0
                then 'A'
                when not is_ed_ea_flagged and submitted_early_count > 0
                then 'B'
            end as section,
        from {{ ref("int_students__early_applications_rollup") }}
    )

select
    _dbt_source_project,
    overgrad_student_id,
    section,
    student_name,
    high_school,
    counselor_name,
    gpa_band,
    will_apply_early_applications,
    earliest_will_apply_due_date,
    submitted_early_applications,
    submitted_no_deadline_type_applications,

    case
        section
        when 'A'
        then 'A. Flagged ED/EA, no early app submitted'
        when 'B'
        then
            'B. Submitted early, but the Is ED/EA flag is not Yes: '
            || 'check the flag in Overgrad'
    end as section_label,
from sectioned
where section is not null
