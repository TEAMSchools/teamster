select
    {{ dbt_utils.generate_surrogate_key(["c.course_number", "c._dbt_source_project"]) }}
    as course_key,

    c.course_number as course_code,
    c.course_name as course_title,
    c.credittype as credit_type,
    csc.discipline as academic_subject,
    c.credit_hours as credits,

from {{ ref("stg_powerschool__courses") }} as c
left join
    {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }} as csc
    on c.course_number = csc.powerschool_course_number
