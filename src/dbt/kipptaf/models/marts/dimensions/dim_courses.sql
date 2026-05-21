select
    -- FK source_relation must match dim_course_sections, which is built from
    -- base_powerschool__sections. Rewrite c's source relation to the parent's.
    -- TODO: replace() is a no-op if a future district uses a different base
    -- model name. Long-term fix: hash region prefix only, consistent across
    -- producer and consumer (#3820).
    {{
        dbt_utils.generate_surrogate_key(
            [
                "c.course_number",
                (
                    "replace(c._dbt_source_relation,"
                    " 'stg_powerschool__courses',"
                    " 'base_powerschool__sections')"
                ),
            ]
        )
    }} as course_key,

    c.course_number as course_code,
    c.course_name as course_title,
    c.credittype as credit_type,
    csc.discipline as academic_subject,
    c.credit_hours as credits,

from {{ ref("stg_powerschool__courses") }} as c
left join
    {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }} as csc
    on c.course_number = csc.powerschool_course_number
