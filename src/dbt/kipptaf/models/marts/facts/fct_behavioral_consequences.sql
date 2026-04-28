with
    enrollments as (
        select
            student_number,
            academic_year,
            entrydate,
            _dbt_source_relation,

            row_number() over (
                partition by student_number, academic_year, _dbt_source_relation
                order by entrydate desc
            ) as rn,
        from {{ ref("base_powerschool__student_enrollments") }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "p.incident_id",
                "p.incident_penalty_id",
                "p._dbt_source_relation",
            ]
        )
    }} as behavioral_consequence_key,

    {{ dbt_utils.generate_surrogate_key(["p.incident_id", "p._dbt_source_relation"]) }}
    as behavioral_incident_key,

    p.start_date as start_date_key,
    p.end_date as end_date_key,

    p.penalty_name as `type`,
    p.suspension_type,
    p.num_days as days_assigned,
    p.num_periods as periods_assigned,

    p.is_suspension,
    p.is_reportable,
from {{ ref("int_deanslist__incidents__penalties") }} as p
inner join
    enrollments as enr
    on p.student_school_id = enr.student_number
    and p.create_ts_academic_year = enr.academic_year
    and {{ union_dataset_join_clause(left_alias="p", right_alias="enr") }}
    and enr.rn = 1
where p.incident_penalty_id is not null
