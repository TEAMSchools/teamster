with
    date_spine as (
        select date_day,
        from
            unnest(
                generate_date_array(
                    /* first date of the attrition snapshot*/
                    '2002-07-01',
                    current_date('{{ var("local_timezone") }}'),
                    interval 1 year
                )
            ) as date_day
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
        from date_spine
        where extract(month from date_day) = 7 and extract(day from date_day) = 1
    ),

    denom as (
        select distinct
            d.academic_year, d.attrition_date, d.effective_date, srh.employee_number,
        from {{ ref("int_people__staff_roster_history") }} as srh
        inner join
            dates as d
            on (
                (
                    srh.effective_date_start <= d.denominator_start_date
                    and srh.effective_date_end >= d.effective_date
                )
                or (
                    srh.effective_date_start
                    between d.denominator_start_date and d.effective_date
                )
                or (
                    srh.effective_date_end
                    between d.denominator_start_date and d.effective_date
                )
            )
        where
            srh.primary_indicator
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

            if(
                srh.assignment_status in ('Terminated', 'Deceased'),
                coalesce(srh.assignment_status_reason, 'Missing/no Reason'),
                null
            ) as termination_reason,

            if(
                srh.assignment_status in ('Terminated', 'Deceased'), 1, 0
            ) as is_attrition,

            max(srh.worker_termination_date) over (
                partition by srh.employee_number
            ) as termination_date,
        from denom as dc
        inner join
            {{ ref("int_people__staff_roster_history") }} as srh
            on dc.employee_number = srh.employee_number
            and dc.attrition_date
            between srh.effective_date_start and srh.effective_date_end
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
            termination_date,
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

            if(
                srh.assignment_status in ('Terminated', 'Deceased'), 1, 0
            ) as is_attrition,

            coalesce(
                max(srh.worker_termination_date) over (
                    partition by srh.employee_number
                ),
                srh.effective_date_start
            ) as termination_date,
        from denom as dc
        inner join
            {{ ref("int_people__staff_roster_history") }} as srh
            on dc.employee_number = srh.employee_number
            and dc.attrition_date
            between srh.effective_date_start and srh.effective_date_end
            and srh.assignment_status in ('Terminated', 'Deceased')
        left join
            active_next_year as an
            on  dc.academic_year = an.academic_year
            and srh.employee_number = an.employee_number 
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
            termination_date,

            sum(1) over (
                partition by employee_number order by academic_year
            ) as year_at_kipp,  /* Counting year as the year a person is in*/

            sum(
                if(
                    job_title in (
                        'Teacher',
                        'Teacher in Residence',
                        'Learning Specialist',
                        'Teacher ESL',
                        'Teacher,ESL',
                        'Teacher in Residence ESL',
                        'Co-Teacher',
                        'Co-Teacher_historical'
                    ),
                    1,
                    0
                )
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
            cat.termination_date,

            srh.powerschool_teacher_number,
            srh.formatted_name,
            srh.home_business_unit_name,
            srh.home_work_location_powerschool_school_id,
            srh.home_work_location_name,
            srh.home_work_location_abbreviation,
            srh.home_work_location_grade_band,
            srh.home_department_name,
            srh.job_title,
            srh.base_remuneration_annual_rate_amount,
            srh.additional_remunerations_rate_amount,
            srh.reports_to_employee_number,
            srh.reports_to_formatted_name,
            srh.gender_identity,
            srh.race_ethnicity_reporting,
            srh.community_grew_up,
            srh.community_professional_exp,
            srh.level_of_education,
            srh.alumni_status,
            srh.worker_original_hire_date as original_hire_date,

            coalesce(srh.years_exp_outside_kipp, 0)
            + cat.years_teaching_at_kipp as total_years_teaching,
        from core_attrition_table as cat
        inner join
            {{ ref("int_people__staff_roster_history") }} as srh
            /* where you worked on 4/30 is the reporting data */
            on cat.effective_date
            between srh.effective_date_start and srh.effective_date_end
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
            termination_date,
            powerschool_teacher_number,
            formatted_name,
            home_business_unit_name,
            home_work_location_powerschool_school_id,
            home_work_location_name,
            home_work_location_abbreviation,
            home_work_location_grade_band,
            home_department_name,
            job_title,
            base_remuneration_annual_rate_amount,
            additional_remunerations_rate_amount,
            reports_to_employee_number,
            reports_to_formatted_name,
            gender_identity,
            race_ethnicity_reporting,
            community_grew_up,
            community_professional_exp,
            level_of_education,
            alumni_status,
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
            cat.termination_date,
            srh.powerschool_teacher_number,
            srh.formatted_name,
            srh.home_business_unit_name,
            srh.home_work_location_powerschool_school_id,
            srh.home_work_location_name,
            srh.home_work_location_abbreviation,
            srh.home_work_location_grade_band,
            srh.home_department_name,
            srh.job_title,
            srh.base_remuneration_annual_rate_amount,
            srh.additional_remunerations_rate_amount,
            srh.reports_to_employee_number,
            srh.reports_to_formatted_name,
            srh.gender_identity,
            srh.race_ethnicity_reporting,
            srh.community_grew_up,
            srh.community_professional_exp,
            srh.level_of_education,
            srh.alumni_status,
            srh.worker_original_hire_date as original_hire_date,

            coalesce(srh.years_exp_outside_kipp, 0)
            + cat.years_teaching_at_kipp as total_years_teaching,
        from core_attrition_table as cat
        inner join
            {{ ref("int_people__staff_roster_history") }} as srh
            /* where you worked on 4/30 is the reporting data */
            on cat.effective_date
            between srh.effective_date_start and srh.effective_date_end
            and cat.employee_number = srh.employee_number
            and srh.job_title != 'Intern'
            and srh.assignment_status in ('Terminated', 'Deceased')
        left join
            ly_active as lya
            on cat.academic_year = srh.employee_number
            and cat.employee_number = lya.employee_number
        where lya.employee_number is null
    ),

    ly_deduped as (
        select
            academic_year,
            employee_number,
            is_attrition,
            year_at_kipp,
            termination_reason,
            powerschool_teacher_number,
            formatted_name,
            home_business_unit_name,
            home_work_location_powerschool_school_id,
            home_work_location_name,
            home_work_location_abbreviation,
            home_work_location_grade_band,
            home_department_name,
            job_title,
            base_remuneration_annual_rate_amount,
            additional_remunerations_rate_amount,
            reports_to_employee_number,
            reports_to_formatted_name,
            gender_identity,
            race_ethnicity_reporting,
            community_grew_up,
            community_professional_exp,
            level_of_education,
            alumni_status,
            termination_date,
            original_hire_date,
            total_years_teaching,

            if(
                count(employee_number) over (
                    partition by employee_number, academic_year
                )
                > 1
                and termination_reason
                in ('Import Created Action', 'Upgrade Created Action'),
                'dupe',
                'not dupe'
            ) as dupe_check,
        from ly_combined
    )

select distinct
    l.academic_year,
    l.employee_number,
    l.is_attrition,
    l.year_at_kipp,
    l.termination_reason,
    l.powerschool_teacher_number,
    l.formatted_name as preferred_name_lastfirst,
    l.home_business_unit_name as business_unit_home_name,
    l.home_work_location_powerschool_school_id as ps_school_id,
    l.home_work_location_name,
    l.home_work_location_abbreviation,
    l.home_work_location_grade_band,
    l.home_department_name as department_home_name,
    l.job_title,
    l.base_remuneration_annual_rate_amount
    as base_remuneration_annual_rate_amount_amount_value,
    l.additional_remunerations_rate_amount as additional_remuneration_rate_amount_value,
    l.reports_to_employee_number as report_to_employee_number,
    l.reports_to_formatted_name as report_to_preferred_name_lastfirst,
    l.gender_identity,
    l.race_ethnicity_reporting,
    l.community_grew_up,
    l.community_professional_exp,
    l.level_of_education,
    l.alumni_status,
    l.original_hire_date,
    l.termination_date,
    l.total_years_teaching,
from ly_deduped as l
where l.dupe_check != 'dupe'
