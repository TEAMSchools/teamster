{{
    config(
        severity="warn",
        store_failures=true,
        store_failures_as="view",
        meta={
            "dagster": {
                "ref": {"name": "int_powerschool__gpa_cumulative"},
            },
        },
    )
}}

with
    gpa_with_enrollment as (
        select
            g._dbt_source_relation,
            g.studentid,
            g.schoolid,
            g.cumulative_y1_gpa,
            g.cumulative_y1_gpa_unweighted,

            e.academic_year,
            e.enroll_status,
            e.grade_level,
            e.year_in_school,
        from {{ ref("int_powerschool__gpa_cumulative") }} as g
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as e
            on g._dbt_source_relation = e._dbt_source_relation
            and g.studentid = e.studentid
            and g.schoolid = e.schoolid
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.enroll_status = 0
            and e.rn_year = 1
    )

select
    _dbt_source_relation,
    studentid,
    schoolid,
    academic_year,
    cumulative_y1_gpa,
    cumulative_y1_gpa_unweighted,
    grade_level,
    year_in_school,
    'unweighted exceeds weighted' as test_failure_reason,
from gpa_with_enrollment
where cumulative_y1_gpa_unweighted > cumulative_y1_gpa

union all

select
    _dbt_source_relation,
    studentid,
    schoolid,
    academic_year,
    cumulative_y1_gpa,
    cumulative_y1_gpa_unweighted,
    grade_level,
    year_in_school,
    'cumulative gpa is null' as test_failure_reason,
from gpa_with_enrollment
where
    cumulative_y1_gpa is null
    and schoolid != 999999
    and grade_level >= 9
    and year_in_school > 1
    and current_date(
        '{{ var("local_timezone") }}'
    ) between date({{ var("current_academic_year") }}, 10, 15) and date(
        {{ var("current_academic_year") + 1 }}, 06, 15
    )
