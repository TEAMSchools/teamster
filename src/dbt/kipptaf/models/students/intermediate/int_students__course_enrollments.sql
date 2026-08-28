with
    -- coalesce guards an empty int_focus__schedule (an unbuilt --defer dev
    -- copy): min(academic_year) over no rows is NULL, and NULL >=
    -- fay.min_academic_year evaluates to NULL rather than false, so `not (...)`
    -- is NULL too and the WHERE filter drops every Miami row instead of keeping
    -- the archive. 9999 fails toward preserving the data that exists.
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

            -- PowerSchool has no separate departure date: cc_dateleft is the
            -- actual leave date when the student left and the term end plus a
            -- day while the enrollment is open. It is therefore already the
            -- neutral concept, and is non-null on all 751,359 rows since 2004.
            a.cc_dateleft as scheduled_end_date,

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
            -- Term dates, not event dates -- see the column descriptions. A
            -- future-term row therefore carries a future date. #5002
            s.start_date as cc_dateenrolled,
            s.end_date as cc_dateleft,

            -- Focus records the departure and the scheduled term end as two
            -- facts; PowerSchool conflates them into cc_dateleft. Resolve the
            -- neutral column from whichever this SIS actually has, rather than
            -- back-filling PowerSchool's conflated column. #5043
            coalesce(s.end_date, s.marking_period_end_date) as scheduled_end_date,
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

            -- An inferred flag; the derivation and its measurement are in the
            -- column description. Two things this expression does not show:
            -- the window excludes a withdrawal sweep, which closes every one of
            -- a leaver's rows at once, and the coalesce is required rather than
            -- defensive -- end_date is null on 96.8% of Miami rows and
            -- `null < date` is null, so without it the flag reads null on every
            -- open row. #4968
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
