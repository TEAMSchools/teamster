with
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

    denom as (
        select distinct
            d.academic_year, d.attrition_date, d.effective_date, srh.employee_number,
        from {{ ref("base_people__staff_roster_history") }} as srh
        inner join
            dates as d
            on (
                date(srh.work_assignment_start_date) <= d.denominator_start_date
                and date(srh.work_assignment_end_date) >= d.effective_date
            )
            or (
                date(srh.work_assignment_start_date)
                between d.denominator_start_date and d.effective_date
            )
            or (
                date(srh.work_assignment_end_date)
                between d.denominator_start_date and d.effective_date
            )
        where
            srh.primary_indicator = true
            and srh.assignment_status not in ('Terminated', 'Deceased')
            and srh.job_title != 'Intern'
            and coalesce(srh.assignment_status_reason, 'Missing/no Reason')
            != 'Internship Ended'
    ),

    active_next_year as (
        select
            dc.academic_year,
            dc.effective_date,
            dc.employee_number,
            srh.job_title,
            srh.assignment_status,
            case
                when srh.assignment_status in ('Terminated', 'Deceased')
                then coalesce(srh.assignment_status_reason, 'Missing/no Reason')
            end as termination_reason,
            case
                when srh.assignment_status in ('Terminated', 'Deceased') then 1 else 0
            end as is_attrition,
        from denom as dc
        inner join
            {{ ref("base_people__staff_roster_history") }} as srh
            on dc.attrition_date between date(srh.work_assignment_start_date) and date(
                srh.work_assignment_end_date
            )
            and dc.employee_number = srh.employee_number
            and srh.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
    ),

    combined_statuses as (
        select
            academic_year,
            effective_date,
            employee_number,
            job_title,
            assignment_status,
            termination_reason,
            is_attrition,
        from active_next_year

        union all

        select
            dc.academic_year,
            dc.effective_date,
            dc.employee_number,
            srh.job_title,
            srh.assignment_status,
            case
                when srh.assignment_status in ('Terminated', 'Deceased')
                then coalesce(srh.assignment_status_reason, 'Missing/no Reason')
            end as termination_reason,
            case
                when srh.assignment_status in ('Terminated', 'Deceased') then 1 else 0
            end as is_attrition,
        from denom as dc
        inner join
            {{ ref("base_people__staff_roster_history") }} as srh
            on dc.attrition_date between date(srh.work_assignment_start_date) and date(
                srh.work_assignment_end_date
            )
            and dc.employee_number = srh.employee_number
            and srh.assignment_status in ('Terminated', 'Deceased')
        left join
            active_next_year as an
            on an.academic_year = dc.academic_year
            and an.employee_number = srh.employee_number
        /* removing duplicate rows - entity changers + rehires have ongoing term rows*/
        where an.employee_number is null
    ),

    core_attrition_table as (
        select
            academic_year,
            effective_date,
            employee_number,
            termination_reason,
            is_attrition,
            sum(1) over (
                partition by employee_number order by academic_year
            ) as year_at_kipp,  /* Counting year as the year a person is in*/
            sum(
                case
                    when
                        job_title in (
                            'Teacher',
                            'Teacher in Residence',
                            'Learning Specialist',
                            'Teacher ESL',
                            'Teacher,ESL',
                            'Teacher in Residence ESL',
                            'Co-Teacher',
                            'Co-Teacher_historical'
                        )
                    then 1
                    else 0
                end
            ) over (partition by employee_number order by academic_year)
            as years_teaching_at_kipp,  /* Counting year as the year a person is in*/
        from combined_statuses
    ),

    ly_active as (
        select
            cat.academic_year,
            cat.employee_number,
            cat.is_attrition,
            cat.year_at_kipp,
            cat.termination_reason,
            srh.preferred_name_lastfirst,
            srh.business_unit_home_name,
            srh.home_work_location_name,
            srh.home_work_location_abbreviation,
            srh.home_work_location_grade_band,
            srh.department_home_name,
            srh.job_title,
            srh.base_remuneration_annual_rate_amount_amount_value,
            srh.additional_remuneration_rate_amount_value,
            srh.report_to_employee_number,
            srh.gender_identity,
            srh.race_ethnicity_reporting,
            srh.community_grew_up,
            srh.community_professional_exp,
            srh.primary_grade_level_taught,
            srh.level_of_education,
            srh.alumni_status,
            srh.worker_termination_date as termination_date,
            srh.worker_original_hire_date as original_hire_date,
            coalesce(srh.years_exp_outside_kipp, 0)
            + cat.years_teaching_at_kipp as total_years_teaching,
        from core_attrition_table as cat
        inner join
            {{ ref("base_people__staff_roster_history") }} as srh
            on cat.effective_date between date(srh.work_assignment_start_date) and date(
                srh.work_assignment_end_date
            )  /* where you worked on 4/30 is the reporting data*/
            and cat.employee_number = srh.employee_number
            and srh.job_title != 'Intern'
            and srh.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
    ),

    ly_combined as (
        select
            academic_year,
            employee_number,
            is_attrition,
            year_at_kipp,
            termination_reason,
            preferred_name_lastfirst,
            business_unit_home_name,
            home_work_location_name,
            home_work_location_abbreviation,
            home_work_location_grade_band,
            department_home_name,
            job_title,
            base_remuneration_annual_rate_amount_amount_value,
            additional_remuneration_rate_amount_value,
            report_to_employee_number,
            gender_identity,
            race_ethnicity_reporting,
            community_grew_up,
            community_professional_exp,
            primary_grade_level_taught,
            level_of_education,
            alumni_status,
            termination_date,
            original_hire_date,
            total_years_teaching,
        from ly_active

        union all

        select
            cat.academic_year,
            cat.employee_number,
            cat.is_attrition,
            cat.year_at_kipp,
            cat.termination_reason,
            srh.preferred_name_lastfirst,
            srh.business_unit_home_name,
            srh.home_work_location_name,
            srh.home_work_location_abbreviation,
            srh.home_work_location_grade_band,
            srh.department_home_name,
            srh.job_title,
            srh.base_remuneration_annual_rate_amount_amount_value,
            srh.additional_remuneration_rate_amount_value,
            srh.report_to_employee_number,
            srh.gender_identity,
            srh.race_ethnicity_reporting,
            srh.community_grew_up,
            srh.community_professional_exp,
            srh.primary_grade_level_taught,
            srh.level_of_education,
            srh.alumni_status,
            srh.worker_termination_date as termination_date,
            srh.worker_original_hire_date as original_hire_date,
            coalesce(srh.years_exp_outside_kipp, 0)
            + cat.years_teaching_at_kipp as total_years_teaching,
        from core_attrition_table as cat
        inner join
            {{ ref("base_people__staff_roster_history") }} as srh
            on cat.effective_date between date(srh.work_assignment_start_date) and date(
                srh.work_assignment_end_date
            )  /* where you worked on 4/30 is the reporting data*/
            and cat.employee_number = srh.employee_number
            and srh.job_title != 'Intern'
            and srh.assignment_status in ('Terminated', 'Deceased')
        left join
            ly_active as lya
            on lya.academic_year = cat.academic_year
            and lya.employee_number = cat.employee_number
        where lya.employee_number is null
    ),

    ly_deduped as (
        select
            academic_year,
            employee_number,
            is_attrition,
            year_at_kipp,
            termination_reason,
            preferred_name_lastfirst,
            business_unit_home_name,
            home_work_location_name,
            home_work_location_abbreviation,
            home_work_location_grade_band,
            department_home_name,
            job_title,
            base_remuneration_annual_rate_amount_amount_value,
            additional_remuneration_rate_amount_value,
            report_to_employee_number,
            gender_identity,
            race_ethnicity_reporting,
            community_grew_up,
            community_professional_exp,
            primary_grade_level_taught,
            level_of_education,
            alumni_status,
            termination_date,
            original_hire_date,
            total_years_teaching,
            case
                when
                    count(employee_number) over (
                        partition by employee_number, academic_year
                    )
                    > 1
                    and termination_reason
                    in ('Import Created Action', 'Upgrade Created Action')
                then 'dupe'
                else 'not dupe'
            end as dupe_check,
        from ly_combined
    ),

    pm_scores as (
        select employee_number, academic_year, overall_score, overall_tier,
        from {{ ref("int_performance_management__overall_scores") }}
        where pm_term = 'PM4'
    )

select distinct
    l.academic_year,
    l.employee_number,
    l.is_attrition,
    l.year_at_kipp,
    l.termination_reason,
    l.preferred_name_lastfirst,
    l.business_unit_home_name,
    l.home_work_location_name,
    l.home_work_location_abbreviation,
    l.home_work_location_grade_band,
    l.department_home_name,
    l.job_title,
    l.base_remuneration_annual_rate_amount_amount_value,
    l.additional_remuneration_rate_amount_value,
    l.report_to_employee_number,
    l.gender_identity,
    l.race_ethnicity_reporting,
    l.community_grew_up,
    l.community_professional_exp,
    l.primary_grade_level_taught,
    l.level_of_education,
    l.alumni_status,
    l.termination_date,
    l.original_hire_date,
    l.total_years_teaching,
    pm.overall_tier,
from ly_deduped as l
left join
    pm_scores as pm
    on l.employee_number = pm.employee_number
    and l.academic_year = pm.academic_year
where l.dupe_check != 'dupe'
