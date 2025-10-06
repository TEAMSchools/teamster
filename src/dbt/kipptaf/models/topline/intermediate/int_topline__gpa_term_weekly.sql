with
    -- trunk-ignore(sqlfluff/ST03)
    gpa_term as (
        select
            _dbt_source_relation,
            studentid,
            schoolid,
            yearid,
            dbt_valid_from,
            dbt_valid_to,
            gpa_y1,

            cast(dbt_valid_from as date) as dbt_valid_from_date,
            cast(dbt_valid_to as date) as dbt_valid_to_date,
        from {{ ref("snapshot_powerschool__gpa_term") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="gpa_term",
                partition_by="_dbt_source_relation, studentid, schoolid, yearid, dbt_valid_from_date",
                order_by="dbt_valid_to desc",
            )
        }}
    )

select
    co.student_number,
    co.schoolid,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,
    co.week_number_academic_year,

    gpa.gpa_y1,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
left join
    deduplicate as gpa
    on co.studentid = gpa.studentid
    and co.schoolid = gpa.schoolid
    and co.yearid = gpa.yearid
    and co.week_start_monday between gpa.dbt_valid_from_date and gpa.dbt_valid_to_date
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
where co.is_enrolled_week and co.school_level in ('MS', 'HS')
