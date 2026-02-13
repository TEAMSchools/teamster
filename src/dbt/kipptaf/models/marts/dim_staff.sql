with
    roster_history as (
        select distinct
            _dbt_source_relation,
            formatted_name,
            effective_date_start,
            assignment_status,
            assignment_status_reason,
            home_business_unit_name as entity,
            home_work_location_grade_band as grade_band,
            home_work_location_name as `location`,
            home_department_name as department,
            job_title,
            reports_to_employee_number,
            reports_to_formatted_name as manager_name,
            base_remuneration_annual_rate_amount as salary,
            employee_number,
            powerschool_teacher_number,
            languages_spoken,
            race_ethnicity_reporting,
            gender_identity,

            /* key for rows with relevant changes */
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "employee_number",
                        "assignment_status",
                        "home_business_unit_name",
                        "home_work_location_name",
                        "home_department_name",
                        "job_title",
                        "base_remuneration_annual_rate_amount",
                    ]
                )
            }} as surrogate_key,

            /* assignment academic year to each row for annual aggregations */
            {{
                date_to_fiscal_year(
                    date_field="effective_date_start",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,
        from {{ ref("int_people__staff_roster_history") }}
        where primary_indicator and assignment_status != 'Pre-Start'
    ),

    dedupe as (
        select
            *,

            lag(surrogate_key, 1, '') over (
                partition by employee_number order by effective_date_start asc
            ) as surrogate_key_lag,
        from roster_history
    ),

    roster as (select *, from dedupe where surrogate_key != surrogate_key_lag),

    grade_levels as (select *, from {{ ref("int_powerschool__teacher_grade_levels") }}),

    performance_management_tiers as (
        select *, from {{ ref("int_performance_management__overall_scores") }}
    ),

    managers as (select distinct reports_to_employee_number, from roster),

    years_experience as (select *, from {{ ref("int_people__years_experience") }})

select
    r.effective_date_start as marts_effective_date_start,
    r.assignment_status,
    r.assignment_status_reason,
    r.employee_number,
    r.formatted_name,
    r.entity,
    r.grade_band,
    r.location,
    r.department,
    r.job_title,
    r.manager_name,
    r.languages_spoken,
    r.race_ethnicity_reporting,
    r.gender_identity,
    r.salary,

    ye.years_experience_total,
    ye.years_teaching_total,

    if(
        r.job_title in (
            'Teacher',
            'Teacher in Residence',
            'ESE Teacher',
            'Learning Specialist',
            'Teacher ESL',
            'Teacher in Residence ESL',
            'Instructor in Residence'
        ),
        true,
        false
    ) as is_teacher,

    if(
        r.employee_number
        in (select managers.reports_to_employee_number, from managers),
        true,
        false
    ) as is_manager,

    lag(r.salary) over (
        partition by r.employee_number order by r.effective_date_start
    ) as previous_salary,

    lag(r.job_title) over (
        partition by r.employee_number order by r.effective_date_start
    ) as previous_job_title,

    coalesce(
        date_sub(
            lead(r.effective_date_start) over (
                partition by r.employee_number order by r.effective_date_start
            ),
            interval 1 day
        ),
        '9999-12-31'
    ) as marts_effective_date_end,

    {{
        dbt_utils.generate_surrogate_key(
            ["r.employee_number", "r.effective_date_start"]
        )
    }} as staff_history_key,
from roster as r
left join
    grade_levels as gl
    on r.powerschool_teacher_number = gl.teachernumber
    and r._dbt_source_relation = gl._dbt_source_project
    and r.academic_year = gl.academic_year
    and gl.grade_level_rank = 1
left join
    performance_management_tiers as pm
    on r.employee_number = pm.employee_number
    and r.academic_year = pm.academic_year
left join
    years_experience as ye
    on r.employee_number = ye.employee_number
    and r.academic_year = ye.academic_year
