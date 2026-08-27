with
    -- Focus is Miami's system of record from AY2026 forward, but the frozen
    -- archive still holds Miami AY2020 through AY2025. Scope by year rather
    -- than excluding Miami wholesale, and derive the boundary so a Focus
    -- backfill of an earlier year does not silently double-count.
    -- coalesce guards against an empty int_focus__schedule (e.g. an unbuilt
    -- --defer dev copy): min(academic_year) with no rows is NULL, and NULL >=
    -- fay.min_academic_year evaluates to NULL rather than false below, so
    -- `not (...)` also evaluates to NULL and the WHERE filter drops every
    -- Miami row instead of keeping the archive. 9999 fails toward preserving
    -- the data that exists.
    focus_academic_year_boundary as (
        select coalesce(min(academic_year), 9999) as min_academic_year,
        from {{ ref("int_focus__schedule") }}
    ),

    powerschool_conformed as (
        select
            a.* except (courses_credittype),

            cx.ap_course_subject,
            cx.block_schedule_session,
            cx.county_code_override,
            cx.course_level,
            cx.course_sequence_code,
            cx.course_span,
            cx.course_type,
            cx.cte_test_name_code,
            cx.ctecollegecredits as cte_college_credits,
            cx.ctetestdevelopercode as cte_test_developer_code,
            cx.ctetestname as cte_test_name,
            cx.district_code_override,
            cx.dual_institution,
            cx.exclude_course_submission_tf,
            cx.nces_course_id,
            cx.nces_subject_area,
            cx.school_code_override,
            cx.sla_include_tf,

            csc.illuminate_subject_area,
            csc.is_foundations,
            csc.is_advanced_math,
            csc.discipline,

            {{ extract_region("a") }} as region,

            case
                when a.courses_credittype in ('ENG', 'ELA')
                then 'ENG'
                when a.courses_credittype in ('MATH', 'Math')
                then 'MATH'
                when a.courses_credittype in ('SCI', 'Science')
                then 'SCI'
                when a.courses_credittype in ('HR', 'Homeroom')
                then 'HR'
                else a.courses_credittype
            end as courses_credittype,

            if(cx.ap_course_subject is not null, true, false) as is_ap_course,

            if(
                csc.discipline = 'SOC', 'Civics', csc.discipline
            ) as standardized_discipline,

            coalesce(a.cc_course_number like 'HR%', false) as is_homeroom,

            row_number() over (
                partition by
                    a._dbt_source_relation, a.cc_studyear, csc.illuminate_subject_area
                order by a.cc_termid desc, a.cc_dateenrolled desc, a.cc_dateleft desc
            ) as rn_student_year_illuminate_subject_desc,

        from {{ ref("int_powerschool__course_enrollments_union") }} as a
        cross join focus_academic_year_boundary as fay
        left join
            {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
            on a.courses_dcid = cx.coursesdcid
            and a._dbt_source_project = cx._dbt_source_project
        left join
            {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }} as csc
            on a.cc_course_number = csc.powerschool_course_number
        where
            not (
                a._dbt_source_project = 'kippmiami'
                and a.cc_academic_year >= fay.min_academic_year
            )
    ),

    focus_conformed as (
        select
            s._dbt_source_relation,
            s.student_schedule_id as cc_dcid,
            s.academic_year as cc_academic_year,
            s.course_period_id as sections_dcid,
            s.course_period_id as cc_sectionid,
            -- Term dates, not event dates. A Focus schedule start_date is
            -- the marking period's start, so cc_dateenrolled is the term start
            -- rather than the day the student joined the section, and every
            -- future-term row carries a future date. cc_dateleft is null while
            -- the row is open, which is the normal state. Documented with the
            -- measurement on int_focus__schedule. See #5002.
            s.start_date as cc_dateenrolled,
            s.end_date as cc_dateleft,
            st.student_number as students_student_number,
            loc.powerschool_school_id as sections_schoolid,
            loc.powerschool_school_id as cc_schoolid,
            c.short_name as cc_course_number,
            s._dbt_source_project,

            {{ extract_region("s") }} as region,

            coalesce(
                sr_ein.powerschool_teacher_number, sr_email.powerschool_teacher_number
            ) as teachernumber,

            -- Focus's homeroom boolean is null on every row; identified by
            -- title instead, matching int_focus__advisory. See #4868.
            coalesce(s.course_title like 'Homeroom%', false) as is_homeroom,

            -- Focus has no `sectionid < 0` convention; it closes a schedule
            -- row by setting end_date. A row whose end_date falls before its
            -- term ends, while the student still holds an open row, is an
            -- unenrollment before the expected end -- a dropped section. This
            -- is an INFERENCE, not a vendor-documented flag, and PowerSchool
            -- derives the same column a different way, so the two regions reach
            -- one meaning by two routes.
            --
            -- The surviving-open-row test is what excludes a withdrawal sweep:
            -- leaving the school closes every one of the student's rows at
            -- once, which is a consequence of leaving rather than a drop. It
            -- stands in for PowerSchool's own `dateleft = exitdate` exclusion.
            -- PowerSchool's second exclusion, a year-end close, needs no
            -- equivalent: zero Focus rows end at or after their term's end.
            --
            -- The coalesce is load-bearing, not defensive. end_date is null
            -- on 96.8% of Miami rows (an open schedule row, the normal state),
            -- and `null < date` is null, so without it the flag reads null on
            -- every open row -- reinstating the exact bug this replaces, since
            -- `not null` is null and silently removes Miami from every report
            -- using the bare `not is_dropped_section` idiom (#4996).
            --
            -- Measured 2026-08-27: 576 of 19,363 Miami AY2026 rows (2.97%)
            -- across 84 students, against a like-for-like NJ band of 0.23%
            -- (Paterson) to 8.55% (Camden), with Newark at 2.63%. A derivation
            -- joined to the student's stint agrees on 19,358 of 19,363 rows.
            -- See #4968.
            coalesce(
                s.end_date < s.marking_period_end_date
                and countif(s.end_date is null) over (
                    partition by s.student_id, s.academic_year
                )
                > 0,
                false
            ) as is_dropped_section,

            -- New Jersey state reporting crosswalk; Miami is Florida, so
            -- correctly absent rather than deferred.
            cast(null as bool) as is_ap_course,
        from {{ ref("int_focus__schedule") }} as s
        inner join
            {{ ref("int_focus__students") }} as st on s.student_id = st.student_id
        inner join {{ ref("int_focus__courses") }} as c on s.course_id = c.course_id
        inner join {{ ref("int_focus__schools") }} as sch on s.schoolid = sch.id
        left join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on sch.school_number = loc.focus_school_id
        left join
            {{ ref("int_focus__users") }} as usr
            on s.teacher_id = usr.staff_id
            and s._dbt_source_project = usr._dbt_source_project
        left join
            {{ ref("int_people__staff_roster") }} as sr_ein
            on safe_cast(usr.ein as int64) = sr_ein.employee_number
        left join
            {{ ref("int_people__staff_roster") }} as sr_email
            on lower(usr.e_mail_address) = lower(sr_email.google_email)
    ),

    -- is_dropped_course mirrors PowerSchool's derivation in
    -- base_powerschool__course_enrollments: true only when every section of
    -- that course is dropped for the student-year. It needs its own scope
    -- because BigQuery does not allow a window function inside another
    -- window function's argument.
    focus_course_dropped as (
        select
            *,

            avg(if(is_dropped_section, 1, 0)) over (
                partition by
                    _dbt_source_project,
                    students_student_number,
                    cc_academic_year,
                    cc_course_number
            )
            = 1.0 as is_dropped_course,
        from focus_conformed
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_course_dropped
