{{- config(materialized="table") -}}

select
    c.semester,
    c.quarter,
    c.school_level,
    c.week_number_quarter,
    c.week_start_monday,
    c.week_end_sunday,
    c.school_week_start_date_lead as audit_due_date,

    ge.region,
    ge.academic_year,
    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,

    sec._dbt_source_relation,
    sec.sections_id as sectionid,
    sec.sections_schoolid as schoolid,
    sec.teachernumber as teacher_number,
    sec.terms_yearid as yearid,

    a.assignmentid as teacher_assign_id,
    a.name as teacher_assign_name,
    a.duedate as teacher_assign_due_date,
    a.scoretype as teacher_assign_score_type,
    a.totalpointvalue as teacher_assign_max_score,

    asg.n_students,
    asg.n_late,
    asg.n_exempt,
    asg.n_missing,
    asg.n_expected,
    asg.n_expected_scored,
    asg.avg_expected_scored_percent
    as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    count(a.assignmentid) over (
        partition by
            sec._dbt_source_relation,
            sec.sections_id,
            c.quarter,
            ge.assignment_category_code
        order by c.week_number_quarter asc
    ) as teacher_running_total_assign_by_cat,

from {{ ref("int_powerschool__calendar_week") }} as c
inner join
    {{ ref("stg_reporting__gradebook_expectations") }} as ge
    on c.academic_year = ge.academic_year
    and c.region = ge.region
    and c.quarter = ge.quarter
    and c.week_number_quarter = ge.week_number
    and c.school_level = ge.school_level
left join
    {{ ref("base_powerschool__sections") }} as sec
    on c.schoolid = sec.sections_schoolid
    and c.yearid = sec.terms_yearid
    and c.week_end_date between sec.terms_firstday and sec.terms_lastday
    and {{ union_dataset_join_clause(left_alias="c", right_alias="sec") }}
    /* exclude courses */
    and sec.courses_course_number not in (
        'LOG20',  -- Early Dismissal
        'LOG300',  -- Study Hall
        'SEM22101G1',  -- Student Government
        'SEM22106G1',  -- Advisory
        'SEM22106S1',  -- Not in SY24-25 yet
        /* Lunch */
        'LOG100',
        'LOG1010',
        'LOG11',
        'LOG12',
        'LOG22999XL',
        'LOG9'
    )
    /* exclude courses at specific schools */
    and concat(sec.sections_schoolid, sec.sections_course_number) not in (
        '73252SEM72250G1',
        '73252SEM72250G2',
        '73252SEM72250G3',
        '73252SEM72250G4',
        '133570965SEM72250G1',
        '133570965SEM72250G2',
        '133570965SEM72250G3',
        '133570965SEM72250G4',
        '732514GYM08035G1',
        '732514GYM08036G2',
        '732514GYM08037G3',
        '732514GYM08038G4'
    )
left join
    {{ ref("int_powerschool__gradebook_assignments") }} as a
    on sec.sections_dcid = a.sectionsdcid
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="a") }}
    and ge.assignment_category_name = a.category_name
    and a.duedate between c.week_start_monday and c.week_end_sunday
left join
    {{ ref("int_powerschool__assignment_score_rollup") }} as asg
    on a.assignmentsectionid = asg.assignmentsectionid
    and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}
where
    /* exclude F & S categories for iReady courses */
    concat(sec.sections_course_number, a.category_code) not in (
        'SEM72005G1F',
        'SEM72005G2F',
        'SEM72005G3F',
        'SEM72005G4F',
        'SEM72005G1S',
        'SEM72005G2S',
        'SEM72005G3S',
        'SEM72005G4S'
    )
    and sec.terms_firstday = '{{ var("current_academic_year") }}-07-01'
