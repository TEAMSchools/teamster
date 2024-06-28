select
    sr.employee_number,
    sr.preferred_name_lastfirst,
    t.type,
    t.code,
    t.name as rubric,
    t.academic_year,
    t.is_current,
    o.observation_id,
    o.observed_at,

from {{ ref("base_people__staff_roster") }} as sr
cross join {{ ref("stg_reporting__terms") }} as t
left join
    {{ ref("int_performance_management__observations") }} as o
    on t.type = o.observation_type_abbreviation
    and o.observed_at between t.start_date and t.end_date
where
    sr.job_title in ("Teacher", "Teacher in Residence", "Learning Specialist")
    and sr.assignment_status = 'Active'
    and t.type in ('PMS', 'PMC', 'TR', 'O3', 'WT')
    and t.academic_year = {{ var("current_academic_year") }}
    and t.is_current
