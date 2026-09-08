with
    elementary_grade as (
        select teachernumber, max(grade_level) as max_grade_level,
        from {{ ref("int_students__teacher_grade_levels") }}
        where academic_year = {{ var("current_academic_year") }}
        group by teachernumber
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by sheet layout
select
    c.employee_number as df_employee_number,
    if(c.is_prestart, 'Pre-Start', c.assignment_status) as `status`,
    c.formatted_name as preferred_name,
    c.home_work_location_name as primary_site,
    c.job_title as primary_job,
    c.home_department_name as primary_on_site_department,
    c.mail,
    c.google_email,
    c.worker_original_hire_date as original_hire_date,
    c.home_business_unit_name as entity,

    null as pm1,
    null as pm2,
    null as pm3,
    -- TODO: rename
    -- trunk-ignore(sqlfluff/RF05)
    null as `last year final`,
    null as intent_to_return,
    null as reason_for_leaving_primary,
    null as reason_for_leaving_secondary,
    null as transfer_1,
    null as transfer_oe,
    null as stay_oe,
    null as anything_else_oe,
    if(
        c.home_department_name = 'Elementary' and g.max_grade_level is not null,
        concat(c.home_department_name, ', Grade ', g.max_grade_level),
        c.home_department_name
    ) as department_grade,
from {{ ref("int_people__staff_roster") }} as c
left join elementary_grade as g on c.powerschool_teacher_number = g.teachernumber
where c.assignment_status not in ('Terminated')
