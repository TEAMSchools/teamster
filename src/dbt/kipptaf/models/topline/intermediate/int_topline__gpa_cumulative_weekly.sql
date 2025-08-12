with
    gpa_cumulative_date as (
        select
            _dbt_source_relation,
            studentid,
            schoolid,
            cumulative_y1_gpa_projected_unweighted,
            dbt_valid_from,

            date(dbt_valid_from) as dbt_valid_from_date,
            date(dbt_valid_to) as dbt_valid_to_date,
        from {{ ref("snapshot_powerschool__gpa_cumulative") }}
    ),

    gpa_cumulative as (
        select
            _dbt_source_relation,
            studentid,
            schoolid,
            cumulative_y1_gpa_projected_unweighted,
            dbt_valid_from_date,
            dbt_valid_to_date,

            row_number() over (
                partition by
                    _dbt_source_relation, studentid, schoolid, dbt_valid_from_date
                order by dbt_valid_from desc
            ) as rn_date,
        from gpa_cumulative_date
    )

select
    gpa._dbt_source_relation,
    gpa.studentid,
    gpa.schoolid,
    gpa.cumulative_y1_gpa_projected_unweighted,

    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.week_number_academic_year,
from {{ ref("int_powerschool__calendar_week") }} as cw
inner join
    gpa_cumulative as gpa
    on cw.schoolid = gpa.schoolid
    and cw.week_start_monday between gpa.dbt_valid_from_date and gpa.dbt_valid_to_date
    and rn_date = 1
