with
    latest_status_calc as (
        select
            r.enrollment_academic_year,
            r.enrollment_academic_year_display,
            r.org,
            r.region,
            r.schoolid,
            r.finalsite_enrollment_id as finalsite_id,
            r.powerschool_student_number,
            r.first_name,
            r.last_name,
            r.grade_level,
            r.enrollment_type,
            r.self_contained,
            r.gender,
            r.birthdate,
            r.detailed_status,
            r.status_start_date,
            r.status_order,

            x.status_group_name,
            x.status_group_value,
            x.grouped_status_order,
            x.grouped_status_timeframe,

            'All' as aligned_enrollment_type,

            if(
                x.status_group_value in ('Inquiries', 'Applications'),
                r.region,
                r.school
            ) as school,

            first_value(r.detailed_status) over (
                partition by r.finalsite_enrollment_id
                order by r.status_start_date desc, r.status_order desc
            ) as latest_status,

        from {{ ref("int_finalsite__status_report_unpivot") }} as r
        inner join
            {{ ref("int_google_sheets__finalsite__status_crosswalk_unpivot") }} as x
            on r._dagster_partition_key = x._dagster_partition_key
            and r.enrollment_type = x.enrollment_type
            and r.detailed_status = x.detailed_status
            and x.valid_detailed_status
            and not x.qa_flag
        where r.enrollment_academic_year = {{ var("finalsite_recruitment_year") }}
    ),

    -- trunk-ignore(sqlfluff/ST03)
    start_dates as (
        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            schoolid,
            school,
            finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            gender,
            birthdate,
            self_contained,
            enrollment_type,
            aligned_enrollment_type,
            status_group_value as grouped_status,
            grouped_status_order,
            grouped_status_timeframe,
            latest_status,

            max(status_start_date) over (
                partition by finalsite_id, status_group_value
            ) as grouped_status_start_date,

        from latest_status_calc
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="start_dates",
                partition_by="finalsite_id, grouped_status",
                order_by="grouped_status_start_date desc",
            )
        }}
    ),

    roster as (
        -- ever statuses
        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            schoolid,
            school,
            finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            gender,
            birthdate,
            self_contained,
            enrollment_type,
            grouped_status,
            latest_status,
            aligned_enrollment_type,
            grouped_status_order,
            grouped_status_timeframe,
            grouped_status_start_date,

            case
                when
                    grouped_status in (
                        'Accepted to Enrolled',
                        'Offers to Accepted',
                        'Offers to Enrolled'
                    )
                then 'Conversion'
                else grouped_status
            end as goal_type,

            case
                grouped_status
                when 'Applications'
                then 'App Target'
                when 'Offers'
                then 'Offers Target'
                else grouped_status
            end as goal_name,

        from deduplicate
        where grouped_status_timeframe = 'Ever'

        union all

        -- regular current
        select
            r.enrollment_academic_year,
            r.enrollment_academic_year_display,
            r.org,
            r.region,
            r.schoolid,
            r.school,
            r.finalsite_id,
            r.powerschool_student_number,
            r.first_name,
            r.last_name,
            r.grade_level,
            r.gender,
            r.birthdate,
            r.self_contained,
            r.enrollment_type,
            r.grouped_status,
            r.latest_status,
            r.aligned_enrollment_type,
            r.grouped_status_order,
            r.grouped_status_timeframe,
            r.grouped_status_start_date,

            case
                when
                    r.grouped_status in (
                        'Accepted to Enrolled Num',
                        'Offers to Accepted Num',
                        'Offers to Enrolled Num'
                    )
                then 'Conversion'
                else r.grouped_status
            end as goal_type,

            r.grouped_status as goal_name,

        from deduplicate as r
        inner join
            {{ ref("int_google_sheets__finalsite__status_crosswalk_unpivot") }} as u
            on r.enrollment_academic_year = u.file_year
            and r.enrollment_type = u.enrollment_type
            and r.grouped_status_timeframe = u.grouped_status_timeframe
            and r.latest_status = u.detailed_status
            and r.grouped_status = u.status_group_value
        where r.grouped_status_timeframe = 'Current'
    ),

    add_group_status_end_date as (
        select
            enrollment_academic_year,
            finalsite_id,
            enrollment_type,
            goal_type,
            goal_name,
            grouped_status,
            grouped_status_order,
            grouped_status_start_date,

            lead(grouped_status_start_date, 1, current_date('America/New_York')) over (
                partition by finalsite_id
                order by grouped_status_start_date asc, grouped_status_order asc
            ) as grouped_status_end_date,

        from roster
        where grouped_status_order != 0 and enrollment_type = 'New'
    ),

    days_in_grouped_status_calc as (
        select
            enrollment_academic_year,
            finalsite_id,
            enrollment_type,
            goal_type,
            goal_name,
            grouped_status,
            grouped_status_order,
            grouped_status_start_date,
            grouped_status_end_date,

            if(
                grouped_status_end_date = grouped_status_start_date,
                1,
                date_diff(grouped_status_end_date, grouped_status_start_date, day)
            ) as days_in_grouped_status,

        from add_group_status_end_date
    ),

    filter_days_in_status as (
        select
            * except (goal_name),

            case
                when goal_name = 'Pending Offers' and days_in_grouped_status <= 4
                then '<= 4 Days'
                when
                    goal_name = 'Pending Offers'
                    and days_in_grouped_status between 5 and 10
                then '>= 5 & <= 10 Days'
                when goal_name = 'Pending Offers' and days_in_grouped_status > 10
                then '> 10 Days'
                else goal_name
            end as goal_name,

        from days_in_grouped_status_calc
    ),

    finalsite_contact_ids as (
        select
            _dbt_source_project,
            finalsite_enrollment_id,

            cast(focus_student_id_prefixed as int) as focus_student_id,
        from {{ ref("int_finalsite__contact_id_attributes") }}
    ),

    -- The Focus vertical (int_focus__student_enrollment_roster) carries no
    -- Finalsite identity of its own -- this crosswalk join is what blends the
    -- two sources, so it belongs here (the consumer), not in the Focus
    -- wrapper. Inner join keeps only Focus enrollments that match a Finalsite
    -- contact record.
    focus_enrollments_with_finalsite as (
        select
            e.academic_year,
            e.ps_schoolid,
            e.school,
            e.student_number,
            e.grade_level,
            e.enroll_status,
            e.startdate as sis_entry_date,
            e.is_enrolled_oct01,
            e.is_enrolled_oct15,
            e.is_enrolled_mar15,

            f.finalsite_enrollment_id,
        from {{ ref("int_focus__student_enrollment_roster") }} as e
        inner join
            finalsite_contact_ids as f
            on e.student_number = f.focus_student_id
            and e._dbt_source_project = f._dbt_source_project
        where
            e.rn_year = 1 and e.academic_year = {{ var("finalsite_recruitment_year") }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    enrollment_lookup as (
        select
            academic_year,
            schoolid,
            school,
            infosnap_id,
            student_number,
            grade_level,
            enroll_status,
            entrydate as sis_entry_date,
            is_enrolled_oct01,
            is_enrolled_oct15,
            is_enrolled_mar15,

        from {{ ref("int_extracts__student_enrollments") }}
        where
            rn_year = 1
            and infosnap_id is not null
            and academic_year = {{ var("finalsite_recruitment_year") }}

        union all

        select
            academic_year,
            ps_schoolid as schoolid,
            school,
            finalsite_enrollment_id as infosnap_id,
            student_number,
            grade_level,
            enroll_status,
            sis_entry_date,
            is_enrolled_oct01,
            is_enrolled_oct15,
            is_enrolled_mar15,

        from focus_enrollments_with_finalsite
    ),

    -- rn_year is computed per student, so two PowerSchool records sharing one
    -- infosnap_id both carry rn_year = 1 and fan out the enrollment joins below.
    -- Prefer the actively-enrolled record, then the newest student record.
    -- TODO: remove once the duplicate PowerSchool student records are merged (#4326)
    -- Cross-source tiebreak: when a student appears in both the frozen
    -- pre-migration PowerSchool snapshot and live Focus data with the same
    -- enroll_status, student_number desc prefers the Focus record (Focus ids
    -- are 10-digit FLDOE-prefixed, PowerSchool ids are shorter) -- intentional:
    -- Focus is Miami's live SIS. TODO(#4326) covers duplicate PS records.
    deduplicate_enrollments as (
        {{
            dbt_utils.deduplicate(
                relation="enrollment_lookup",
                partition_by="academic_year, infosnap_id",
                order_by="(enroll_status = 0) desc, student_number desc",
            )
        }}
    ),

    expanded_roster as (
        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            schoolid,
            school,
            finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            gender,
            birthdate,
            self_contained,
            enrollment_type,
            latest_status,
            aligned_enrollment_type,
            grouped_status_timeframe,

            goal_type,

            goal_name,

        from roster

        union all

        -- moved here to not include these expanded goal types in days in status calc
        select
            d.enrollment_academic_year,
            d.enrollment_academic_year_display,
            d.org,
            d.region,
            d.schoolid,
            d.school,
            d.finalsite_id,
            d.powerschool_student_number,
            d.first_name,
            d.last_name,
            d.grade_level,
            d.gender,
            d.birthdate,
            d.self_contained,
            d.enrollment_type,
            d.latest_status,
            d.aligned_enrollment_type,
            d.grouped_status_timeframe,

            d.grouped_status as goal_type,

            grouped_status_expand as goal_name,

        from deduplicate as d
        cross join
            unnest(
                ['<= 4 Days', '>= 5 & <= 10 Days', '> 10 Days']
            ) as grouped_status_expand
        where
            d.grouped_status_timeframe = 'Current'
            and d.grouped_status = 'Pending Offers'
    ),

    final_roster as (

        -- maintain pending offers general
        select
            r.enrollment_academic_year,
            r.enrollment_academic_year_display,
            r.org,
            r.region,
            r.schoolid,
            r.school,
            r.finalsite_id,
            r.powerschool_student_number,
            r.first_name,
            r.last_name,
            r.grade_level,
            r.gender,
            r.birthdate,
            r.self_contained,
            r.enrollment_type,
            r.latest_status,
            r.aligned_enrollment_type,
            r.grouped_status_timeframe,
            r.goal_name,
            r.goal_type,

            d.days_in_grouped_status,

            e.enroll_status,
            e.grade_level as sis_grade_level,
            e.schoolid as sis_schoolid,
            e.school as sis_school,
            e.sis_entry_date,
            e.is_enrolled_oct01,
            e.is_enrolled_oct15,
            e.is_enrolled_mar15,

            case
                when r.latest_status = 'Enrolled'
                then 0
                when
                    r.latest_status in (
                        -- left
                        'Mid Year Withdrawal',
                        'Never Attended',
                        'Summer Withdraw',
                        -- pending
                        'Accepted',
                        'Assigned School',
                        'Did Not Enroll',
                        'Campus Transfer Requested',
                        'Parent Declined',
                        'Enrollment In Progress'
                    )
                then 2
            end as finalsite_expected_enroll_status,

        from expanded_roster as r
        left join
            filter_days_in_status as d
            on r.enrollment_academic_year = d.enrollment_academic_year
            and r.finalsite_id = d.finalsite_id
            and r.enrollment_type = d.enrollment_type
            and r.goal_type = d.goal_type
            and r.goal_name = d.goal_name
        left join
            deduplicate_enrollments as e
            on r.enrollment_academic_year = e.academic_year
            and r.finalsite_id = e.infosnap_id
        where r.goal_name not in ('<= 4 Days', '>= 5 & <= 10 Days', '> 10 Days')

        union all
        -- ensure pending offers timeframes have day in status
        select
            r.enrollment_academic_year,
            r.enrollment_academic_year_display,
            r.org,
            r.region,
            r.schoolid,
            r.school,
            r.finalsite_id,
            r.powerschool_student_number,
            r.first_name,
            r.last_name,
            r.grade_level,
            r.gender,
            r.birthdate,
            r.self_contained,
            r.enrollment_type,
            r.latest_status,
            r.aligned_enrollment_type,
            r.grouped_status_timeframe,
            r.goal_name,
            r.goal_type,

            d.days_in_grouped_status,

            e.enroll_status,
            e.grade_level as sis_grade_level,
            e.schoolid as sis_schoolid,
            e.school as sis_school,
            e.sis_entry_date,
            e.is_enrolled_oct01,
            e.is_enrolled_oct15,
            e.is_enrolled_mar15,

            case
                when r.latest_status = 'Enrolled'
                then 0
                when
                    r.latest_status in (
                        -- left
                        'Mid Year Withdrawal',
                        'Never Attended',
                        'Summer Withdraw',
                        -- pending
                        'Accepted',
                        'Assigned School',
                        'Did Not Enroll',
                        'Campus Transfer Requested',
                        'Parent Declined',
                        'Enrollment In Progress'
                    )
                then 2
            end as finalsite_expected_enroll_status,

        from expanded_roster as r
        inner join
            filter_days_in_status as d
            on r.enrollment_academic_year = d.enrollment_academic_year
            and r.finalsite_id = d.finalsite_id
            and r.enrollment_type = d.enrollment_type
            and r.goal_type = d.goal_type
            and r.goal_name = d.goal_name
        left join
            deduplicate_enrollments as e
            on r.enrollment_academic_year = e.academic_year
            and r.finalsite_id = e.infosnap_id
        where r.goal_name in ('<= 4 Days', '>= 5 & <= 10 Days', '> 10 Days')
    ),

    -- Hardcoded FDOS per region; year from finalsite_recruitment_year. Own CTE
    -- because BigQuery rejects a lateral custom_fdos_date reference. Rationale
    -- in fresh-dashboard-data-model.md.
    custom_fdos_dates as (
        select
            *,

            case
                region
                when 'Newark'
                then date({{ var("finalsite_recruitment_year") }}, 8, 28)
                when 'Paterson'
                then date({{ var("finalsite_recruitment_year") }}, 8, 28)
                when 'Camden'
                then date({{ var("finalsite_recruitment_year") }}, 8, 24)
                when 'Miami'
                then date({{ var("finalsite_recruitment_year") }}, 8, 14)
            end as custom_fdos_date,

        from final_roster
    )

select
    *,

    if(
        (finalsite_expected_enroll_status = 0 and enroll_status in (2, 3))
        or (finalsite_expected_enroll_status = 2 and enroll_status = 0),
        true,
        false
    ) as is_enroll_status_mismatch,

    if(grade_level != sis_grade_level, true, false) as is_grade_level_mismatch,

    if(schoolid != sis_schoolid, true, false) as is_school_mismatch,

    -- Bare comparison, not if(..., true, false), so a student with no SIS
    -- record stays null rather than collapsing to false.
    sis_entry_date <= custom_fdos_date as is_enrolled_fdos,

from custom_fdos_dates
