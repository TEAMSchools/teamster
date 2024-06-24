with
    students_assignments as (
        select
            se._dbt_source_relation,
            se.student_number,
            se.academic_year,
            se.grade_level,

            ce.sections_dcid,

            c.semester,
            c.quarter,
            c.week_number_quarter,
            c.week_number_academic_year,
            c.week_start_date,
            c.week_end_date,
            c.school_week_start_date,
            c.school_week_end_date,
            c.school_week_start_date_lead,

            ge.assignment_category_code,
            ge.assignment_category_term,
            ge.expectation,

            a.assignmentid,
            a.name as assignment_name,
            a.duedate,
            a.scoretype,
            a.totalpointvalue,
            a.category_name,

            s.scorepoints,

            coalesce(s.islate, 0) as islate,
            coalesce(s.isexempt, 0) as isexempt,
            coalesce(s.ismissing, 0) as ismissing,

            if(
                a.scoretype = 'PERCENT',
                (a.totalpointvalue * s.scorepoints) / 100,
                s.scorepoints
            ) as score_converted,
        from {{ ref("base_powerschool__student_enrollments") }} as se
        inner join
            {{ ref("base_powerschool__course_enrollments") }} as ce
            on ce.cc_studentid = se.studentid
            and ce.cc_yearid = se.yearid
            and {{ union_dataset_join_clause(left_alias="se", right_alias="ce") }}
            and not ce.is_dropped_section
            and ce.cc_course_number not in (
                'HR',
                'LOG100',
                'LOG1010',
                'LOG11',
                'LOG12',
                'LOG20',
                'LOG22999XL',
                'LOG300',
                'LOG9',
                'SEM22106G1',
                'SEM22106S1'
            )
        inner join
            {{ ref("int_powerschool__calendar_week") }} as c
            on ce.cc_schoolid = c.schoolid
            and ce.cc_yearid = c.yearid
            and c.week_end_date between ce.cc_dateenrolled and ce.cc_dateleft
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="c") }}
        inner join
            {{ ref("stg_reporting__gradebook_expectations") }} as ge
            on c.academic_year = ge.academic_year
            and c.quarter = ge.quarter
            and c.week_number_quarter = ge.week_number
            and c.region = ge.region
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on ce.sections_dcid = a.sectionsdcid
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="a") }}
            and a.duedate between c.week_start_date and c.week_end_date
            and {{ union_dataset_join_clause(left_alias="c", right_alias="a") }}
            and ge.assignment_category_name = a.category_name
            and a.iscountedinfinalgrade = 1
            and a.scoretype in ('POINTS', 'PERCENT')
        left join
            {{ ref("stg_powerschool__assignmentscore") }} as s
            on se.students_dcid = s.studentsdcid
            and {{ union_dataset_join_clause(left_alias="se", right_alias="s") }}
            and a.assignmentsectionid = s.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
        where
            se.academic_year = {{ var("current_academic_year") }}
            and se.rn_year = 1
            and se.enroll_status = 0
            and not se.is_out_of_district
    ),

    audits as (
        select
            _dbt_source_relation,
            student_number,
            academic_year,
            grade_level,
            sections_dcid,

            `quarter` as assign_quarter,
            semester as assign_semester_code,
            week_number_academic_year as audit_yr_week_number,
            week_number_quarter as audit_qt_week_number,
            week_start_date as audit_start_date,
            week_end_date as audit_end_date,
            school_week_start_date_lead as audit_due_date,

            assignment_category_code as assign_category_code,
            category_name as assign_category,
            assignment_category_term as assign_category_quarter,

            assignmentid as assign_id,
            assignment_name as assign_name,
            duedate as assign_due_date,
            scoretype as assign_score_type,
            totalpointvalue as assign_max_score,
            scorepoints as assign_score_raw,
            score_converted as assign_score_converted,
            isexempt as assign_is_exempt,
            islate as assign_is_late,
            ismissing as assign_is_missing,

            safe_divide(score_converted, totalpointvalue)
            * 100 as assign_final_score_percent,

            if(
                score_converted > totalpointvalue, true, false
            ) as assign_score_above_max,

            if(
                assignmentid is not null and isexempt = 0, true, false
            ) as assign_expected_to_be_scored,

            if(
                assignmentid is not null and scorepoints is not null and isexempt = 0,
                true,
                false
            ) as assign_scored,

            if(
                assignmentid is not null and scorepoints is null and isexempt = 0,
                true,
                false
            ) as assign_null_score,

            if(
                assignmentid is not null
                and isexempt = 0
                and (
                    (ismissing = 0 and scorepoints is not null)
                    or scorepoints is not null
                ),
                true,
                false
            ) as assign_expected_with_score,

            if(
                isexempt = 1 and score_converted > 0, true, false
            ) as assign_exempt_with_score,

            if(score_converted < 5, true, false) as assign_score_less_5,

            if(
                score_converted < (totalpointvalue / 2), true, false
            ) as assign_score_less_50p,

            if(
                ismissing = 1 and score_converted != 5, true, false
            ) as assign_missing_score_not_5,
        from students_assignments
    )

select
    *,

    case
        when assign_is_exempt = 1
        then false
        when
            grade_level between 5 and 8
            and assign_final_score_percent
            not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100)
        then true
        when
            grade_level between 9 and 12
            and assign_final_score_percent
            not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 93, 97, 100)
        then true
        else false
    end as assign_score_not_conversion_chart_options,
from audits
