with
    years as (
        select academic_year, academic_year + 1 as next_academic_year,
        from
            unnest(
                generate_array(2002, {{ var("current_academic_year") }})
            ) as academic_year
    ),

    dates as (
        select
            *,

            date(academic_year, 7, 1) as default_entry_date,
            date(academic_year, 9, 1) as denominator_start_date,
            date(next_academic_year, 4, 30) as effective_date,
            date(next_academic_year, 6, 30) as default_exit_date,
            date(next_academic_year, 8, 31) as attrition_date,
        from years
    ),

    terminations as (
        select
            position_id,
            assignment_status__effective_date as termination_effective_date,

            coalesce(
                assignment_status__reason_code__long_name,
                assignment_status__reason_code__short_name
            ) as termination_reason,

            lag(assignment_status__effective_date) over (
                partition by position_id order by assignment_status__effective_date
            ) as termination_effective_date_prev,
        from {{ ref("stg_adp_workforce_now__workers__work_assignments") }}
        where assignment_status__status_code__long_name = 'Terminated'
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
            r.item_id,
            r.employee_number,
            r.worker_id,
            r.position_id,
            r.assignment_status,
            r.given_name,
            r.family_name_1,
            r.ethnicity_code,
            r.gender_code,
            r.worker_original_hire_date,
            r.worker_rehire_date,
            r.home_work_location_grade_band,
            r.home_work_location_reporting_school_id,
            r.race_ethnicity,
            r.is_hispanic,
            r.race_ethnicity_reporting,
            r.gender_identity,
            r.relay_status,
            r.community_grew_up,
            r.community_professional_exp,
            r.alumni_status,
            r.path_to_education,

            y.years_at_kipp_total,
            y.years_teaching_total,
            y.years_experience_total,

            tgl.grade_level,

            coalesce(
                r.worker_rehire_date, r.worker_original_hire_date
            ) as most_recent_hire_date,

            coalesce(
                t.termination_effective_date,
                r.worker_termination_date,
                date(9999, 12, 31)
            ) as most_recent_termination_date,
            coalesce(t.termination_reason, r.assignment_status_reason) as status_reason,
        from {{ ref("int_people__staff_roster") }} as r
        left join
            {{ ref("int_people__years_experience") }} as y
            on r.employee_number = y.employee_number
        left join
            final_termination as t
            on r.position_id = t.position_id
            and t.rn_position_termination_desc = 1
        left join
            {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
            on r.powerschool_teacher_number = tgl.teachernumber
            and tgl.academic_year = {{ var("current_academic_year") }}
            and tgl.grade_level_rank = 1
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
                extract(month from most_recent_termination_date) >= 9,
                extract(year from most_recent_termination_date),
                extract(year from most_recent_termination_date) - 1
            ) as end_academic_year,
        from roster_terminations
    ),

    roster_year_scaffold as (
        select
            r.*,

            y.*,

            if(
                r.assignment_status = 'Terminated'
                and r.end_academic_year = y.academic_year,
                r.most_recent_termination_date,
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
            coalesce(
                if(academic_year = end_academic_year, termination_date, null),
                default_exit_date
            ) as academic_year_exitdate,
        from roster_year_scaffold
    ),

    worker_history_clean as (
        select
            employee_number,
            home_business_unit_name,
            home_department_name,
            home_work_location_name,
            job_title,
            safe_cast(
                assignment_status_effective_date as date
            ) as assignment_status_effective_date_start,
            safe_cast(
                coalesce(
                    lead(assignment_status_effective_date, 1) over (
                        partition by employee_number
                        order by assignment_status_effective_date asc
                    ),
                    work_assignment_termination_date,
                    date(9999, 12, 31)
                ) as date
            ) as assignment_status_effective_date_end,
        from {{ ref("int_people__staff_roster_history") }}
        where primary_indicator
    ),

    scaffold as (
        select
            rys.*,

            w.home_business_unit_name,
            w.home_work_location_name,
            w.home_department_name,
            w.job_title,

            lead(rys.academic_year_exitdate, 1) over (
                partition by rys.position_id order by rys.academic_year
            ) as academic_year_exitdate_next,
        from with_academic_year_exitdate as rys
        left join
            worker_history_clean as w
            on rys.employee_number = w.employee_number
            and rys.effective_date
            between w.assignment_status_effective_date_start
            and w.assignment_status_effective_date_end
        where rys.academic_year_exitdate > rys.academic_year_entrydate
    ),

    with_dates as (
        select
            *,
            coalesce(
                academic_year_exitdate_next, termination_date
            ) as attrition_exitdate,
        from scaffold
    )

select
    wd.employee_number as df_employee_number,
    wd.given_name as preferred_first_name,
    wd.family_name_1 as preferred_last_name,
    wd.ethnicity_code as primary_ethnicity,
    wd.gender_code as gender_reporting,
    wd.academic_year,
    wd.academic_year_entrydate,
    wd.academic_year_exitdate,
    wd.worker_original_hire_date as original_hire_date,
    wd.worker_rehire_date as rehire_date,
    wd.termination_date,
    wd.status_reason,
    wd.race_ethnicity,
    wd.is_hispanic,
    wd.race_ethnicity_reporting,
    wd.gender_identity,
    wd.relay_status,
    wd.community_grew_up,
    wd.community_professional_exp,
    wd.alumni_status,
    wd.path_to_education,
    wd.grade_level as primary_grade_level_taught,
    wd.academic_year_exitdate_next as next_academic_year_exitdate,

    case
        when date_diff(wd.academic_year_exitdate, wd.academic_year_entrydate, day) <= 0
        then 0
        when
            wd.academic_year_exitdate >= wd.denominator_start_date
            and wd.academic_year_entrydate <= wd.effective_date
        then 1
        else 0
    end as is_denominator,

    if(wd.attrition_exitdate <= wd.attrition_date, 1.0, 0.0) as is_attrition,

    coalesce(
        wd.home_business_unit_name, sr.home_business_unit_name
    ) as legal_entity_name,

    coalesce(
        wd.home_work_location_grade_band, sr.home_work_location_grade_band
    ) as primary_site_school_level,

    coalesce(wd.home_work_location_name, sr.home_work_location_name) as primary_site,

    coalesce(
        wd.home_work_location_reporting_school_id,
        sr.home_work_location_reporting_school_id
    ) as primary_site_reporting_schoolid,

    coalesce(
        wd.home_department_name, sr.home_department_name
    ) as primary_on_site_department,

    coalesce(wd.job_title, sr.job_title) as primary_job,

    wd.years_at_kipp_total - date_diff(
        coalesce(sr.worker_termination_date, current_date()),
        wd.academic_year_exitdate,
        day
    )
    / 365.25 as years_at_kipp_total,

    wd.years_experience_total - date_diff(
        coalesce(sr.worker_termination_date, current_date()),
        wd.academic_year_exitdate,
        day
    )
    / 365.25 as years_experience_total,
from with_dates as wd
left join
    {{ ref("int_people__staff_roster") }} as sr
    on wd.employee_number = sr.employee_number
