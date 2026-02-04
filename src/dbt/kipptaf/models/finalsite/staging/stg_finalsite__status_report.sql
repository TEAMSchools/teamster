with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_finalsite", "stg_finalsite__status_report"),
                    source("kippnewark_finalsite", "stg_finalsite__status_report"),
                ]
            )
        }}
    )

select
    _dbt_source_relation,
    finalsite_student_id,
    enrollment_year,
    enrollment_academic_year,
    enrollment_academic_year_display,
    school,
    powerschool_student_number,
    last_name,
    first_name,
    grade_level_name,
    grade_level,
    detailed_status,
    status_start_date,
    status_end_date,
    days_in_status,
    rn,

from union_relations
