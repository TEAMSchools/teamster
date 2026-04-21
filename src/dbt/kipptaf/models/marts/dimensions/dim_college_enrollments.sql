with
    nsc_with_account as (
        select
            n.contact_id,
            n.college_code_branch,
            n.enrollment_begin,
            n.enrollment_end,
            n.enrollment_status,
            n.graduated,
            n.degree_title,
            n.enrollment_major_1,
            n.class_level,
        from {{ ref("stg_nsc__student_tracker") }} as n
        where n.record_found_y_n = 'Y'
    ),

    nsc_with_max_end as (
        select
            contact_id,
            college_code_branch,
            enrollment_begin,
            enrollment_end,
            enrollment_status,
            graduated,
            degree_title,
            enrollment_major_1,
            class_level,

            max(enrollment_end) over (
                partition by contact_id, college_code_branch
            ) as max_enrollment_end,
        from nsc_with_account
    ),

    nsc_tenure as (
        select
            contact_id,
            college_code_branch,

            min(enrollment_begin) as enrollment_start_date,
            max(enrollment_end) as enrollment_end_date,

            countif(graduated = 'Y') > 0 as is_graduated,
            countif(enrollment_status = 'W') > 0 as is_withdrawn,

            max(
                if(enrollment_end = max_enrollment_end, enrollment_status, null)
            ) as latest_enrollment_status,
            max(
                if(enrollment_end = max_enrollment_end, degree_title, null)
            ) as degree_title,
            max(
                if(enrollment_end = max_enrollment_end, enrollment_major_1, null)
            ) as major,
            max(
                if(enrollment_end = max_enrollment_end, class_level, null)
            ) as class_level,
        from nsc_with_max_end
        group by contact_id, college_code_branch
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["r.student_number", "t.college_code_branch"]
        )
    }} as college_enrollment_key,

    {{ dbt_utils.generate_surrogate_key(["r.student_number"]) }} as student_key,

    {{ dbt_utils.generate_surrogate_key(["t.college_code_branch"]) }} as college_key,

    t.enrollment_start_date as start_date_key,
    t.enrollment_end_date as end_date_key,

    t.latest_enrollment_status as enrollment_status,
    t.degree_title,
    t.major,
    t.class_level,
    t.is_graduated,
    t.is_withdrawn,
from nsc_tenure as t
inner join {{ ref("int_kippadb__roster") }} as r on t.contact_id = r.contact_id
