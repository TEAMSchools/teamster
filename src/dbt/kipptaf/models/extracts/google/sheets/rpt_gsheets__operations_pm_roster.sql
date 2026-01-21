with
    roster as (
        select
            employee_number,
            formatted_name,
            job_title,
            home_work_location_name,
            home_work_location_abbreviation,
            reports_to_formatted_name,

            concat(
                formatted_name,
                ' - ',
                coalesce(home_work_location_abbreviation, home_work_location_name),
                ' - [',
                employee_number,
                ']'
            ) as name_dropdown,
        from {{ ref("int_people__staff_roster") }}
        where
            assignment_status in ('Active', 'Leave')
            and home_department_name = 'Operations'
            and not contains_substr(home_business_unit_code, 'KIPP_TAF')
            and not contains_substr(job_title, 'Director')
            and job_title != 'Intern'
    )

select
    roster.employee_number,
    roster.formatted_name,
    roster.job_title,
    roster.home_work_location_name,
    roster.home_work_location_abbreviation,
    roster.reports_to_formatted_name,

    -- trunk-ignore(sqlfluff/RF05)
    roster.name_dropdown as `Ops Teammate Name`,
from roster
