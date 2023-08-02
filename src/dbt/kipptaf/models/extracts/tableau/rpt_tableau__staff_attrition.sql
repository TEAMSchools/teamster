with
    terminations as (
        select
            position_id,
            assignment_status_effective_date as termination_effective_date,
            ifnull(
                assignment_status_reason_long_name, assignment_status_reason_short_name
            ) as termination_reason,

            lag(assignment_status_effective_date) over (
                partition by position_id order by assignment_status_effective_date
            ) as termination_effective_date_prev
        from {{ source("adp_workforce_now", "work_assignment_history") }}
        where assignment_status_long_name = 'Terminated' and _fivetran_active
    ),

    /* final termination record */
    final_termination as (
        select
            *,
            row_number() over (
                partition by position_id order by termination_effective_date desc
            ) as rn_position_termination_desc,
        from terminations
        where
            termination_effective_date_prev is null
            or date_diff(
                termination_effective_date, termination_effective_date_prev, day
            )
            > 1
    ),

    roster_terminations as (
        select
            r.work_assignment_id,
            r.employee_number,
            r.worker_id,
            r.position_id,
            r.assignment_status,
            r.preferred_name_given_name,
            r.preferred_name_family_name,
            r.ethnicity_long_name,
            r.gender_long_name,
            r.worker_original_hire_date,
            r.worker_rehire_date,
            r.worker_termination_date,
            r.home_work_location_grade_band,
            r.home_work_location_reporting_school_id,
            null as kipp_alumni_status,
            ifnull(
                r.worker_rehire_date, r.worker_original_hire_date
            ) as most_recent_hire_date,

            t.termination_effective_date,

            ifnull(t.termination_reason, r.assignment_status_reason) as status_reason,
        from {{ ref("base_people__staff_roster") }} as r
        left join
            final_termination as t
            on r.position_id = t.position_id
            and t.rn_position_termination_desc = 1
    ),

    with_academic_year as (
        select
            *,
            if(
                extract(month from most_recent_hire_date) >= 9,
                extract(year from most_recent_hire_date),
                extract(year from most_recent_hire_date) - 1
            ) as start_academic_year,
            if(
                extract(month from worker_termination_date) >= 9,
                extract(year from worker_termination_date),
                extract(year from worker_termination_date) - 1
            ) as end_academic_year,
        from roster_terminations
    ),

    dates as (
        select
            extract(year from date_day) as academic_year,
            extract(year from date_day) + 1 as next_academic_year,

            date(extract(year from date_day), 7, 1) as default_entry_date,
            date((extract(year from date_day) + 1), 6, 30) as default_exit_date,

            date(extract(year from date_day), 9, 1) as denominator_start_date,
            date((extract(year from date_day) + 1), 8, 31) as attrition_date,

            date((extract(year from date_day) + 1), 4, 30) as effective_date,
        from {{ ref("utils__date_spine") }}
        where extract(month from date_day) = 7 and extract(day from date_day) = 1
    ),

    roster_year_scaffold as (
        select
            r.*,

            y.*,

            if(
                r.assignment_status = 'Terminated'
                and r.end_academic_year = y.academic_year,
                ifnull(r.termination_effective_date, r.worker_termination_date),
                null
            ) as termination_date,

            if(
                r.start_academic_year = y.academic_year,
                r.most_recent_hire_date,
                y.default_entry_date
            ) as academic_year_entrydate,
        from with_academic_year as r
        inner join
            dates as y
            on y.academic_year between r.start_academic_year and r.end_academic_year
    ),

    with_academic_year_exitdate as (
        select
            *,
            ifnull(
                if(academic_year = end_academic_year, termination_date, null),
                default_exit_date
            ) as academic_year_exitdate,
        from roster_year_scaffold
    ),

    scaffold as (
        select
            rys.*,

            w.work_assignment_job_title as job_title,
            w.organizational_unit_business_unit_home_name as business_unit_home_name,
            w.organizational_unit_department_home_name as department_home_name,
            ifnull(
                w.work_assignment_home_work_location_name_long_name,
                w.work_assignment_home_work_location_name_short_name
            ) as home_work_location_name,

            lead(rys.academic_year_exitdate, 1) over (
                partition by rys.position_id order by rys.academic_year
            ) as academic_year_exitdate_next,
        from with_academic_year_exitdate as rys
        left join
            {{ ref("base_adp_workforce_now__worker_person") }} as w
            on rys.worker_id = w.work_assignment_worker_id
            and rys.effective_date
            between cast(w.work_assignment__fivetran_start as date) and cast(
                w.work_assignment__fivetran_end as date
            )
            and not w.worker__fivetran_deleted
        where rys.academic_year_exitdate > rys.academic_year_entrydate
    ),

    with_dates as (
        select
            *,
            ifnull(academic_year_exitdate_next, termination_date) as attrition_exitdate,
        from scaffold
    )

select
    employee_number as df_employee_number,
    preferred_name_given_name as preferred_first_name,
    preferred_name_family_name as preferred_last_name,
    ethnicity_long_name as primary_ethnicity,
    gender_long_name as gender_reporting,
    academic_year,
    academic_year_entrydate,
    academic_year_exitdate,
    worker_original_hire_date as original_hire_date,
    worker_rehire_date as rehire_date,
    termination_date,
    status_reason,
    job_title as primary_job,
    department_home_name as primary_on_site_department,
    home_work_location_name as primary_site,
    business_unit_home_name as legal_entity_name,
    home_work_location_reporting_school_id as primary_site_reporting_schoolid,
    home_work_location_grade_band as primary_site_school_level,
    kipp_alumni_status,
    academic_year_exitdate_next as next_academic_year_exitdate,

    case
        when date_diff(academic_year_exitdate, academic_year_entrydate, day) <= 0
        then 0
        when
            academic_year_exitdate >= denominator_start_date
            and academic_year_entrydate <= effective_date
        then 1
        else 0
    end as is_denominator,

    if(attrition_exitdate <= attrition_date, 1.0, 0.0) as is_attrition,

    if(
        most_recent_hire_date > attrition_exitdate,
        round(date_diff(attrition_exitdate, worker_original_hire_date, day) / 365, 0),
        round(date_diff(attrition_exitdate, most_recent_hire_date, day) / 365, 0)
    ) as years_at_kipp,
from with_dates
