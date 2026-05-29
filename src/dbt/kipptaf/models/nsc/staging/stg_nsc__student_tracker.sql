with
    nsc_raw as (
        select
            your_unique_identifier,
            first_name,
            middle_initial,
            last_name,
            name_suffix,
            requester_return_field,
            record_found_y_n,
            college_code_branch,
            college_name,
            college_state,
            two_year_four_year,
            public_private,
            enrollment_status,
            graduated,
            degree_title,
            class_level,
            enrollment_major_1,
            enrollment_major_2,
            degree_major_1,
            degree_major_2,
            degree_major_3,
            degree_major_4,

            cast(college_sequence as int) as college_sequence,
            cast(degree_cip_1 as int) as degree_cip_1,
            cast(degree_cip_2 as int) as degree_cip_2,
            cast(degree_cip_3 as int) as degree_cip_3,
            cast(degree_cip_4 as int) as degree_cip_4,
            cast(enrollment_cip_1 as int) as enrollment_cip_1,
            cast(enrollment_cip_2 as int) as enrollment_cip_2,

            parse_date('%Y%m%d', enrollment_begin) as enrollment_begin,
            parse_date('%Y%m%d', enrollment_end) as enrollment_end,
            parse_date('%Y%m%d', graduation_date) as graduation_date,
            parse_date('%Y%m%d', search_date) as search_date,

            left(
                requester_return_field, length(requester_return_field) - 1
            ) as contact_id_raw,
        from {{ source("nsc", "src_nsc__student_tracker") }}
    )

select
    n.your_unique_identifier,
    n.first_name,
    n.middle_initial,
    n.last_name,
    n.name_suffix,
    n.requester_return_field,
    n.record_found_y_n,
    n.college_code_branch,
    n.college_name,
    n.college_state,
    n.two_year_four_year,
    n.public_private,
    n.enrollment_status,
    n.graduated,
    n.degree_title,
    n.class_level,
    n.enrollment_major_1,
    n.enrollment_major_2,
    n.degree_major_1,
    n.degree_major_2,
    n.degree_major_3,
    n.degree_major_4,
    n.college_sequence,
    n.degree_cip_1,
    n.degree_cip_2,
    n.degree_cip_3,
    n.degree_cip_4,
    n.enrollment_cip_1,
    n.enrollment_cip_2,
    n.enrollment_begin,
    n.enrollment_end,
    n.graduation_date,
    n.search_date,

    /* NSC uppercases the requester_return_field echo; recover canonical
       mixed-case Salesforce ID via case-insensitive contact lookup so
       downstream joins to kippadb succeed. */
    coalesce(c.id, n.contact_id_raw) as contact_id,
from nsc_raw as n
left join
    {{ ref("stg_kippadb__contact") }} as c on upper(n.contact_id_raw) = upper(c.id)
