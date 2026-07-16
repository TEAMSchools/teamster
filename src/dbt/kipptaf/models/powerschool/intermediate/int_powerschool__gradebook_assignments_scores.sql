with
    scores as (
        select
            a._dbt_source_project,
            a.assignmentsectionid,
            a.sectionsdcid,
            a.assignmentid,
            a.name as assignment_name,
            a.duedate,
            a.scoretype,
            a.totalpointvalue,
            a.category_name,
            a.category_code,
            a.iscountedinfinalgrade,

            s.scorepoints,
            s.actualscoreentered,

            e.cc_academic_year as academic_year,
            e.students_dcid,
            e.courses_credittype as credit_type,

            coalesce(s.islate, 0) as is_late,
            coalesce(s.isexempt, 0) as is_exempt,
            coalesce(s.ismissing, 0) as is_missing,

            initcap(regexp_extract(a._dbt_source_project, r'kipp(\w+)')) as region,

            -- no due-date grace period: the 7-day grace scoped for AY
            -- 2026-2027 was dropped as policy (July 2026), see design spec
            case
                when coalesce(s.isexempt, 0) = 1
                then false
                when a.iscountedinfinalgrade = 0
                then false
                else true
            end as is_expected,

            /* hardcoding year while we look for a better solution to custom grade
               level vs school level */
            if(
                e.cc_academic_year >= 2025
                and e.cc_schoolid = 179905
                and e.sections_grade_level = 5,
                'MS',
                d.school_level
            ) as school_level_alt,

            if(
                a.scoretype = 'POINTS',
                s.scorepoints,
                safe_cast(s.actualscoreentered as numeric)
            ) as score_entered,

            if(a.scoretype = 'POINTS', s.scorepoints, null) as points_earned,

            if(
                a.scoretype in ('PERCENT', 'GRADESCALE', 'COLLECTED'),
                safe_cast(s.actualscoreentered as float64),
                null
            ) as numeric_grade_earned,

            if(
                a.scoretype = 'POINTS',
                round(safe_divide(s.scorepoints, a.totalpointvalue) * 100, 2),
                safe_cast(s.actualscoreentered as numeric)
            ) as assign_final_score_percent,

            (a.totalpointvalue / 2) as half_total_point_value,

        from {{ ref("int_powerschool__gradebook_assignments") }} as a
        /* PS automatically assigns ALL assignments to a student when they enroll into
        a section, including those from before their enrollment date. This join ensures
        assignments are only matched to valid student enrollments */
        inner join
            {{ ref("base_powerschool__course_enrollments") }} as e
            on a.sectionsdcid = e.sections_dcid
            and a.duedate >= e.cc_dateenrolled
            and a.duedate < e.cc_dateleft
            and a._dbt_source_project = e._dbt_source_project
            and not e.is_dropped_section
        left join
            {{ ref("stg_powerschool__schools") }} as d
            on e.cc_schoolid = d.school_number
            and e._dbt_source_project = d._dbt_source_project
        left join
            {{ ref("stg_powerschool__assignmentscore") }} as s
            on a.assignmentsectionid = s.assignmentsectionid
            and a._dbt_source_project = s._dbt_source_project
            and e.students_dcid = s.studentsdcid
    ),

    assignment_coding as (
        select
            _dbt_source_project,
            assignmentsectionid,
            sectionsdcid,
            assignmentid,
            assignment_name,
            duedate,
            scoretype,
            totalpointvalue,
            category_name,
            category_code,
            iscountedinfinalgrade,
            scorepoints,
            actualscoreentered,
            academic_year,
            students_dcid,
            credit_type,
            is_late,
            is_exempt,
            is_missing,
            region,
            is_expected,
            school_level_alt,
            score_entered,
            points_earned,
            numeric_grade_earned,
            assign_final_score_percent,
            half_total_point_value,

            if(score_entered = 0, 1, 0) as is_zero,

            if(
                score_entered = 0 and school_level_alt = 'HS' and is_missing = 0, 1, 0
            ) as is_academic_dishonesty,

            if(score_entered is null, 1, 0) as is_null,

            if(score_entered is not null, 1, 0) as is_scored,

            if(is_expected and score_entered = 0, 1, 0) as is_expected_zero,

            if(
                is_expected
                and score_entered = 0
                and school_level_alt = 'HS'
                and is_missing = 0,
                1,
                0
            ) as is_expected_academic_dishonesty,

            if(is_expected and score_entered is null, 1, 0) as is_expected_null,

            if(is_expected and is_late = 1, 1, 0) as is_expected_late,

            if(is_expected and is_missing = 1, 1, 0) as is_expected_missing,

            if(
                is_expected and score_entered is not null, true, false
            ) as is_expected_scored,

        from scores
    )

select
    *,

    if(is_expected_null = 1, true, false) as assign_null_score,

    if(
        is_expected and score_entered > totalpointvalue, true, false
    ) as assign_score_above_max,

    if(
        category_code in ('H', 'W', 'F')
        and is_expected
        and is_missing = 0
        and score_entered < 5,
        true,
        false
    ) as assign_mh_hwf_score_less_5,

    if(
        category_code in ('H', 'W', 'F')
        and school_level_alt = 'MS'
        and is_expected_missing = 1
        and score_entered != 5,
        true,
        false
    ) as assign_ms_hwf_missing_score_not_5,

    if(
        category_code in ('H', 'W', 'F', 'S')
        and school_level_alt = 'HS'
        and is_expected_missing = 1
        and score_entered != 0,
        true,
        false
    ) as assign_hs_hwfs_missing_score_not_0,

    if(
        category_code = 'S'
        and school_level_alt = 'MS'
        and is_expected
        and score_entered < half_total_point_value,
        true,
        false
    ) as assign_ms_s_score_less_50p,

    if(
        category_code = 'S'
        and school_level_alt = 'HS'
        and is_expected
        and is_missing = 0
        and score_entered < half_total_point_value,
        true,
        false
    ) as assign_hs_s_score_less_50p,

from assignment_coding
