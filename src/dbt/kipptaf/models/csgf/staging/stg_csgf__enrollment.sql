with
    calendar_days as (
        select yearid, schoolid, avg(days_total) as total_instructional_days,
        from {{ ref("int_powerschool__calendar_rollup") }}
        where yearid = {{ var("current_academic_year") - 1990 }}
        group by yearid, schoolid
    ),

    students as (
        select
            schoolid,
            student_number,

            case when lunch_status in ('F', 'f', 'R') then 1 else 0 end as frl,

            case
                race_ethnicity
                when 'A'
                then 'Asian'
                when 'B'
                then 'BL/AA'
                when 'H'
                then 'Hispanic or Latino'
                when 'I'
                then 'AI/AN'
                when 'M'
                then 'DTS'
                when 'N'
                then 'DTS'
                when 'P'
                then 'NH/OPI'
                when 'T'
                then '2+ races'
                when 'W'
                then 'White'
                when 'Y'
                then 'DTS'
                else 'DTS'
            end race_ethnicity,

            if(grade_level = 0, 'K', cast(grade_level as string)) as grade_level,

            if(iep_status = 'No IEP', 0, 1) as iep,

            if(lep_status, 1, 0) as ell,

        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and enroll_status = 0
            and rn_year = 1
    ),

    enrollment_counts_pivot as (
        select
            schoolid,

            enrollment_k,
            enrollment_1st,
            enrollment_2nd,
            enrollment_3rd,
            enrollment_4th,
            enrollment_5th,
            enrollment_6th,
            enrollment_7th,
            enrollment_8th,
            enrollment_9th,
            enrollment_10th,
            enrollment_11th,
            enrollment_12th,

        from
            students pivot (
                count(student_number) for grade_level in (
                    'k' as enrollment_k,
                    '1' as enrollment_1st,
                    '2' as enrollment_2nd,
                    '3' as enrollment_3rd,
                    '4' as enrollment_4th,
                    '5' as enrollment_5th,
                    '6' as enrollment_6th,
                    '7' as enrollment_7th,
                    '8' as enrollment_8th,
                    '9' as enrollment_9th,
                    '10' as enrollment_10th,
                    '11' as enrollment_11th,
                    '12' as enrollment_12th
                )
            )
    ),

    enrollment_counts as (
        select
            schoolid,

            sum(enrollment_k) as enrollment_k,
            sum(enrollment_1st) as enrollment_1st,
            sum(enrollment_2nd) as enrollment_2nd,
            sum(enrollment_3rd) as enrollment_3rd,
            sum(enrollment_4th) as enrollment_4th,
            sum(enrollment_5th) as enrollment_5th,
            sum(enrollment_6th) as enrollment_6th,
            sum(enrollment_7th) as enrollment_7th,
            sum(enrollment_8th) as enrollment_8th,
            sum(enrollment_9th) as enrollment_9th,
            sum(enrollment_10th) as enrollment_10th,
            sum(enrollment_11th) as enrollment_11th,
            sum(enrollment_12th) as enrollment_12th,

        from enrollment_counts_pivot
        group by schoolid
    )

select
    c.total_instructional_days,

    et.budget_target as total_budgeted_enrollment,

    ec.enrollment_k,
    ec.enrollment_1st,
    ec.enrollment_2nd,
    ec.enrollment_3rd,
    ec.enrollment_4th,
    ec.enrollment_5th,
    ec.enrollment_6th,
    ec.enrollment_7th,
    ec.enrollment_8th,
    ec.enrollment_9th,
    ec.enrollment_10th,
    ec.enrollment_11th,
    ec.enrollment_12th,

    coalesce(
        case
            r.race_ethnicity_reporting
            when 'Black/African American'
            then 'Black or African American'
            else r.race_ethnicity_reporting
        end,
        'Decline to State'
    ) as race_ethnicity_of_primary_leader,

    coalesce(
        case
            r.gender_identity
            when 'Cis Woman'
            then 'Woman'
            when 'Cis Man'
            then 'Male'
            else r.gender_identity
        end,
        'Not Listed'
    ) as gender_of_primary_leader,

    case
        s.`name`
        when 'Paterson Prep Middle School'
        then 'KIPP Paterson MS'
        when 'Paterson Prep Elementary School'
        then 'KIPP Paterson ES'
        else s.`name`
    end as school,

from {{ ref("stg_powerschool__schools") }} as s
inner join calendar_days as c on s.school_number = c.schoolid
left join
    `kipptaf_google_sheets.stg_google_sheets__topline_enrollment_targets` as et
    on s.school_number = et.schoolid
    and et.academic_year = {{ var("current_academic_year") }}
left join enrollment_counts as ec on s.school_number = ec.schoolid
left join {{ ref("int_people__staff_roster") }} as r on s.principalemail = r.work_email
