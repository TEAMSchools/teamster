/*O3, Walkthroughs, Teacher Development Forms for all academic years*/

select
    observation_id,
    rubric_name,
    observation_score,
    '' as etr_score,
    '' as so_score,
    glows,
    grows,
    last_modified,
    academic_year,
    locked,
    observation_type,
    observation_type_abbreviation,
    row_score,
    measurement_name,
    strand_name,
    strand_description,
    text_box,
    employee_number,
    observer_employee_number,

from {{ ref("int_performance_management__scores") }}
where observation_type_abbreviation in ('O3','WT','TDT')

union all
/*Teacher Performance Management for academic years starting 2024*/

select
    observation_id,
    rubric_name,
    observation_score,
    strand_score,
    glows,
    grows,
    last_modified,
    academic_year,
    locked,
    observation_type,
    observation_type_abbreviation,
    row_score,
    measurement_name,
    strand_name,
    strand_description,
    text_box,
    employee_number,
    observer_employee_number,

from {{ ref("int_performance_management__scores") }}
where observation_type_abbreviation = 'PM'
and academic_year >= 2024

union all

/* Teacher Performance Management 2022 and prior */

select
    os.observation_id,
    os.form_long_name as rubric_name,
    os.overall_score as observation_score,
    os.etr_score as etr_score,
    os.so_score as so.score,
    ds.observed_at as last_modified,
    ds.academic_year,
    null as glows,
    null as grows,
    true as locked,
    'Teacher Performance Management' as observation_type,
    'PM' as observation_type_abbreviation,
    ds.row_score_value as row_score,
    ds.measurement_name,
    '' as strand_name,  /* case for if etr or so row as strand_name*/
    null as strand_description,
    null as text_box,
    os.employee_number,
    ds.observer_employee_number,

from {{ ref("stg_performance_management__scores_overall_archive") }} as os
inner join
    {{ ref("stg_performance_management__scores_detail_archive") }} as ds
    on os.employee_number = ds.employee_number
    and os.academic_year = ds.academic_year
    and os.form_term = ds.form_term
left join
    {{ ref("base_people__staff_roster") }} as sr
    on ds.observer_employee_number = sr.employee_number

/* Teacher Performance Management 2023 */

    
