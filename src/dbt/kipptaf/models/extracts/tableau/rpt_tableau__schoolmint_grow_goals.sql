with
    scaffold as (
        select
            ur.user_id,
            ur.role_name,
            rt.`type`,
            rt.code,
            rt.`name`,
            rt.`start_date`,
            rt.end_date,
            rt.academic_year,
            u.internal_id,
            sr.employee_number,
            sr.preferred_name_lastfirst,
            sr.business_unit_home_name,
            sr.home_work_location_name,
            sr.home_work_location_grade_band,
            sr.home_work_location_powerschool_school_id,
            sr.department_home_name,
            sr.primary_grade_level_taught,
            sr.job_title,
            sr.report_to_preferred_name_lastfirst,
            sr.worker_original_hire_date,
            sr.assignment_status,

        from {{ ref("stg_schoolmint_grow__users__roles") }} as ur
        left join
            {{ ref("stg_reporting__terms") }} as rt on ur.role_name = rt.grade_band
        left join {{ ref("stg_schoolmint_grow__users") }} as u on ur.user_id = u.user_id
        left join
            {{ ref("base_people__staff_roster") }} as sr
            on u.internal_id = safe_cast(sr.employee_number as string)
        where ur.role_name != 'Whetstone' and rt.type = 'O3'
    ),

    microgoals as (
        select
            a.assignment_id,
            a.name as assignment_name,
            a.type as assignment_type,
            a.created as assignment_date,
            a.user_id as teacher_id,
            a.user_name,
            a.creator_id,
            a.creator_name,

            regexp_extract(a.name, r'(\d[A-Z]\.\d\d)') as tag_name_short,

            'O3' as reporting_term_type,
        from {{ ref("stg_schoolmint_grow__assignments") }} as a
    )

select s.*, m.*
from scaffold as s
left join
    microgoals as m
    on cast(m.assignment_date as date) between s.start_date and s.end_date
    and s.type = m.reporting_term_type
    and s.user_id = m.teacher_id
