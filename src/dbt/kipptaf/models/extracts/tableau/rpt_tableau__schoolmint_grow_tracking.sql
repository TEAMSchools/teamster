select
    srh.employee_number,
    srh.preferred_name_lastfirst,

    t.type,
    t.code,
    t.name as rubric,
    t.academic_year,
    t.is_current,

    o.observation_id,
    o.observed_at,

    if(o.observation_id is not null, 1, 0) as is_observed,
from {{ ref("base_people__staff_roster_history") }} as srh
inner join
    {{ ref("stg_reporting__terms") }} as t
    on srh.business_unit_home_name = t.region
    and (
        t.start_date between date(srh.work_assignment_start_date) and date(
            srh.work_assignment_end_date
        )
        or t.end_date between date(srh.work_assignment_start_date) and date(
            srh.work_assignment_end_date
        )
    )
    and t.type in ("PMS", "PMC", "TR", "O3", "WT")
    and t.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("int_performance_management__observations") }} as o
    on srh.employee_number = o.employee_number
    and t.type = o.observation_type_abbreviation
    and o.observed_at between t.start_date and t.end_date
where
    srh.job_title in ("Teacher", "Teacher in Residence", "Learning Specialist")
    and srh.assignment_status = "Active"
