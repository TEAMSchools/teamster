with
    roster_history as (
        select *,
        from {{ ref("int_people__staff_roster_history") }}
        where
            job_title in (
                'Teacher',
                'Teacher in Residence',
                'ESE Teacher',
                'Learning Specialist',
                'Learning Specialist Coordinator'
            )
            and primary_indicator
    ),

    roster_current as (select *, from {{ ref("int_people__staff_roster") }}),

    reporting_terms as (select *, from {{ ref("stg_reporting__terms") }}),

    observations as (
        select *,
        from {{ ref("int_performance_management__observations") }}
        where observation_type_abbreviation in ('WT', 'O3')
    ),

    observation_details as (
        select *, from {{ ref("int_performance_management__observation_details") }}
    ),

    observation_pivot as (
        select
            observations.*,
            max(
                if(
                    measurement_name like '%Teacher Moves Track%',
                    measurement_dropdown_selection,
                    null
                )
            ) as teacher_moves_track,
            max(
                if(
                    measurement_name like '%Student Habits Track%',
                    measurement_dropdown_selection,
                    null
                )
            ) as student_habits_track,
            max(
                if(
                    measurement_name like '%Number%',
                    measurement_dropdown_selection,
                    null
                )
            ) as number_of_kids,
        from observations
        inner join
            observation_details
            on observations.observation_id = observation_details.observation_id
        group by all
    ),

    current_year_tracking as (
        select
            roster_history.employee_number,
            roster_history.formatted_name as teammate,
            roster_history.home_business_unit_name as entity,
            roster_history.home_work_location_name as `location`,
            roster_history.home_work_location_grade_band as grade_band,
            roster_history.home_department_name as department,
            roster_history.job_title,
            roster_history.reports_to_formatted_name as manager,
            roster_history.sam_account_name,
            roster_history.reports_to_sam_account_name,
            roster_history.race_ethnicity_reporting,

            reporting_terms.type,
            reporting_terms.code,
            reporting_terms.name as week,
            reporting_terms.academic_year,
            reporting_terms.is_current,
            reporting_terms.start_date,
            reporting_terms.end_date,

            observation_pivot.observation_id,
            observation_pivot.observed_at,
            observation_pivot.rubric_name,
            observation_pivot.glows,
            observation_pivot.grows,
            observation_pivot.observation_score,
            observation_pivot.teacher_moves_track,
            observation_pivot.student_habits_track,
            observation_pivot.number_of_kids,

            observation_details.strand_name,
            observation_details.measurement_name,
            observation_details.row_score,

            roster_history_manager.formatted_name as observer_name,

            if(observation_pivot.observation_id is not null, 1, 0) as is_observed,

        from roster_history
        inner join
            reporting_terms
            on roster_history.home_business_unit_name = reporting_terms.region
            and reporting_terms.start_date
            between roster_history.effective_date_start
            and roster_history.effective_date_end
        left join
            observation_pivot
            on roster_history.employee_number = observation_pivot.employee_number
            and reporting_terms.type = observation_pivot.observation_type_abbreviation
            and observation_pivot.observed_at
            between reporting_terms.start_date and reporting_terms.end_date
        left join
            observation_details
            on observation_pivot.observation_id = observation_details.observation_id
        left join
            roster_history as roster_history_manager
            on roster_history.employee_number
            = observation_pivot.observer_employee_number
        where
            roster_history.primary_indicator
            and roster_history.assignment_status = 'Active'
            and reporting_terms.academic_year = {{ var("current_academic_year") }}
            and reporting_terms.type in ('WT', 'O3')
    ),

    past_year_reporting as (
        select
            roster_history.employee_number,
            roster_history.formatted_name as teammate,
            roster_history.home_business_unit_name as entity,
            roster_history.home_work_location_name as `location`,
            roster_history.home_work_location_grade_band as grade_band,
            roster_history.home_department_name as department,
            roster_history.job_title,
            roster_history.reports_to_formatted_name as manager,
            roster_history.sam_account_name,
            roster_history.reports_to_sam_account_name,
            roster_history.race_ethnicity_reporting,

            observation_pivot.observation_type_abbreviation,
            cast(null as string) as code,
            cast(null as string) as week,
            observation_pivot.academic_year,
            false is_current,
            cast(null as date) as start_date,
            cast(null as date) as end_date,

            observation_pivot.observation_id,
            observation_pivot.observed_at,
            observation_pivot.rubric_name,
            observation_pivot.glows,
            observation_pivot.grows,
            observation_pivot.observation_score,
            observation_pivot.teacher_moves_track,
            observation_pivot.student_habits_track,
            observation_pivot.number_of_kids,

            observation_details.strand_name,
            observation_details.measurement_name,
            observation_details.row_score,

            roster_observer.formatted_name as observer_name,

            if(observation_pivot.observation_id is not null, 1, 0) as is_observed,
        from observation_pivot
        left join
            roster_history
            on observation_pivot.employee_number = roster_history.employee_number
            and observation_pivot.observed_at
            between roster_history.effective_date_start
            and roster_history.effective_date_end
        left join
            observation_details
            on observation_pivot.observation_id = observation_details.observation_id
        left join
            roster_current as roster_observer
            on observation_pivot.observer_employee_number
            = roster_observer.employee_number
        where
            observation_pivot.academic_year != {{ var("current_academic_year") }}
            and observation_pivot.observation_id is not null
    )

select *
from current_year_tracking

union all

select *
from past_year_reporting
