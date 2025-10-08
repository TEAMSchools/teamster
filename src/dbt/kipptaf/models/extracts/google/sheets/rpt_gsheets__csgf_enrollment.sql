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
            cast(grade_level as string) as grade_level_str,

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

            if(lunch_status in ('F', 'f', 'R', 'FDC'), 1, 0) as frl,

            if(grade_level = 0, 'K', cast(grade_level as string)) as grade_level,

            if(iep_status = 'No IEP', 0, 1) as iep,

            if(lep_status, 1, 0) as ell,

        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and is_enrolled_oct01
            and rn_year = 1
    ),

    enrollment_fields as (select schoolid, student_number, grade_level from students),

    enrollment_counts as (
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
            enrollment_fields pivot (
                count(student_number) for grade_level in (
                    'K' as enrollment_k,
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

    race_fields as (select schoolid, student_number, race_ethnicity, from students),

    race_counts as (
        select
            schoolid,

            ai_an_count,
            asian_count,
            bl_aa_count,
            hispanic_or_latino_count,
            nh_opi_count,
            twoplus_races_count,
            white_count,
            dts_count,

        from
            race_fields pivot (
                count(student_number) for race_ethnicity in (
                    'AI/AN' as ai_an_count,
                    'Asian' as asian_count,
                    'BL/AA' as bl_aa_count,
                    'Hispanic or Latino' as hispanic_or_latino_count,
                    'NH/OPI' as nh_opi_count,
                    '2+ races' as twoplus_races_count,
                    'White' as white_count,
                    'DTS' as dts_count
                )
            )
    ),

    demo_counts as (
        select
            schoolid,

            sum(iep) as iep_count,
            sum(ell) as ell_count,
            sum(frl) as frl_count,

        from students
        group by schoolid
    ),

    retention_counts as (
        select
            py.schoolid,

            count(py.student_number) as retention_denominator,

            sum(if(py.student_number = cy.student_number, 1, 0)) as retention_numerator,

        from {{ ref("int_extracts__student_enrollments") }} as py
        left join
            {{ ref("int_extracts__student_enrollments") }} as cy
            on py.student_number = cy.student_number
            and cy.academic_year = {{ var("current_academic_year") }}
            and (cy.is_enrolled_oct01 or cy.grade_level = 99)
        where
            py.academic_year = {{ var("current_academic_year") - 1 }}
            and py.is_enrolled_oct01
        group by py.schoolid
    ),

    grades_served as (
        select
            schoolid,

            string_agg(
                distinct grade_level_str, ',' order by grade_level_str
            ) as grade_levels_served,

        from students
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

    rc.ai_an_count,
    rc.asian_count,
    rc.bl_aa_count,
    rc.hispanic_or_latino_count,
    rc.nh_opi_count,
    rc.twoplus_races_count,
    rc.white_count,
    rc.dts_count,

    dc.iep_count,
    dc.ell_count,
    dc.frl_count,

    rsc.retention_numerator,
    rsc.retention_denominator,

    gs.grade_levels_served,

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
            then 'Female'
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
    {{ ref("stg_google_sheets__topline_enrollment_targets") }} as et
    on s.school_number = et.schoolid
    and et.academic_year = {{ var("current_academic_year") }}
left join enrollment_counts as ec on s.school_number = ec.schoolid
left join race_counts as rc on s.school_number = rc.schoolid
left join demo_counts as dc on s.school_number = dc.schoolid
left join retention_counts as rsc on s.school_number = rsc.schoolid
left join grades_served as gs on s.school_number = gs.schoolid
left join {{ ref("int_people__staff_roster") }} as r on s.principalemail = r.work_email
