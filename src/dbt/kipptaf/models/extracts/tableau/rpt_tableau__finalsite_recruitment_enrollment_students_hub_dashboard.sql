with
    temp_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_finalsite__status_report"),
                partition_by="surrogate_key",
                order_by="effective_date",
            )
        }}
    ),

    powerschool_roster as (
        select
            _dbt_source_relation,
            academic_year,
            region,
            school_level,
            school_level_alt,
            schoolid,
            school_name,
            school,
            student_number,
            student_name,
            student_first_name,
            student_last_name,
            grade_level,
            enroll_status,
            enroll_status_string,
            entrydate,
            exitdate,
            yearid_prev,
            is_enrolled_oct01,
            is_enrolled_oct15,
            boy_status,

        from {{ ref("int_extracts__student_enrollments") }}
        where grade_level != 99
    )

select *,
from
    powerschool_roster
    {# select
    s.*,

    x.overall_status,
    x.funnel_status,
    x.status_category,
    x.detailed_status_ranking,
    x.powerschool_enroll_status,
    x.valid_detailed_status,
    x.offered,
    x.conversion,
    x.offered_ops,
    x.conversion_ops,

from students as s
left join
    {{ ref("stg_google_sheets__finalsite_status_crosswalk") }} as x
    -- fix this later when int view is fixed
    on s.academic_year = x.enrollment_academic_year
    and s.enrollment_type = x.enrollment_type
    and s.detailed_status = x.detailed_status
 #}
    