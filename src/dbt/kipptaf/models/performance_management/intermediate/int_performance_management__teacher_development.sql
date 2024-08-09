with
    observation_details_pivot as (
        select
            o.employee_number,
            o.observer_employee_number,
            o.observation_id,
            o.rubric_name,
            o.observation_score,
            o.observed_at_timestamp as observed_at,
            o.academic_year,
            o.observation_type,
            o.observation_type_abbreviation,
            o.observation_course,
            o.observation_grade,
            max(
                case when od.measurement_name like '%Grow%' then od.text_box end
            ) as growth_area,
            max(
                case when od.measurement_name like '%Glow%' then od.text_box end
            ) as glow_area,
        from {{ ref("int_performance_management__observations") }} as o
        left join
            {{ ref("int_performance_management__observation_details") }} as od
            on o.observation_id = od.observation_id
        where o.observation_type_abbreviation = 'TDT'
        group by
            o.employee_number,
            o.observer_employee_number,
            o.observation_id,
            o.rubric_name,
            o.observation_score,
            o.observed_at_timestamp,
            o.academic_year,
            o.observation_type,
            o.observation_type_abbreviation,
            o.observation_course,
            o.observation_grade
    )
select
    o.employee_number,
    o.observer_employee_number,
    o.observation_id,
    o.rubric_name,
    o.observation_score,
    o.observed_at,
    o.academic_year,
    o.observation_type,
    o.observation_type_abbreviation,
    o.observation_course as observation_subject,
    o.observation_grade,
    od.row_score,
    od.measurement_name,
    od.strand_name,
    od.text_box,
    p.growth_area,
    p.glow_area,
    null as observer_team,
    null as observer_name
from {{ ref("int_performance_management__observations") }} as o
left join
    {{ ref("int_performance_management__observation_details") }} as od
    on o.observation_id = od.observation_id
left join observation_details_pivot as p on o.observation_id = p.observation_id
where o.observation_type_abbreviation = 'TDT' and od.row_score is not null

union all

select
    o.employee_number,
    null as observer_employee_number,
    o.observation_id,
    concat('Teacher Development: ', o.observation_type) as rubric_name,
    avg(row_score) as observation_score,
    o.observed_at,
    2023 as academic_year,
    'Teacher Development' as observation_type,
    'TDT' as observation_type_abbreviation,
    o.subject as observation_subject,
    null as observation_grade,
    od.row_score,
    od.measurement_name,
    od.strand_name,
    od.text_box,

    o.growth_area,
    o.glow_area,
    o.observer_team,
    o.observer_name,
from {{ ref("stg_performance_management__teacher_development_observations") }} as o
left join
    {{ ref("stg_performance_management__teacher_development_observation_details") }}
    as od
    on o.observation_id = od.observation_id
where row_score is not null
group by
    o.employee_number,
    o.observation_id,
    o.observation_type,
    o.observed_at,
    od.row_score,
    od.measurement_name,
    od.strand_name,
    od.text_box,
    o.subject,
    o.growth_area,
    o.glow_area,
    o.observer_team,
    o.observer_name
