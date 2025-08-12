with
    gpa_cumulative_date as (
        select
            _dbt_source_relation,
            studentid,
            schoolid,
            cumulative_y1_gpa_projected_unweighted,
            dbt_valid_to,
            dbt_valid_from,

            date(dbt_valid_from) as dbt_valid_from_date,
            date(dbt_valid_to) as dbt_valid_to_date,
        from {{ ref("snapshot_powerschool__gpa_cumulative") }}
    ),

    gpa_cumulative as (
        {{
            dbt_utils.deduplicate(
                relation="gpa_cumulative_date",
                partition_by="_dbt_source_relation, studentid, schoolid, dbt_valid_from_date",
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

    gpa.cumulative_y1_gpa_projected_unweighted,
from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as co
left join
    gpa_cumulative as gpa
    on co.studentid = gpa.studentid
    and co.schoolid = gpa.schoolid
    and co.week_start_monday between gpa.dbt_valid_from_date and gpa.dbt_valid_to_date
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
where
    co.discipline = 'ELA'
    and co.is_enrolled_week
    and co.school_level not in ('ES', 'OD')
    and co.grade_level != 99
