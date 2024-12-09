{{- config(materialized="table") -}}

select
    sec._dbt_source_relation,
    sec.sections_id as sectionid,
    sec.teachernumber as teacher_number,
    sec.terms_yearid as yearid,

    c.semester,
    c.quarter,
    c.week_number_quarter,
    c.week_start_monday,
    c.week_end_sunday,
    c.school_week_start_date_lead,

    ge.region,
    ge.school_level,
    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,

    a.assignmentid,
    a.name as assignment_name,
    a.duedate,
    a.scoretype,
    a.totalpointvalue,

    asg.n_students,
    asg.n_late,
    asg.n_exempt,
    asg.n_missing,
    asg.n_expected,
    asg.n_expected_scored,
    asg.avg_expected_scored_percent,

    count(a.assignmentid) over (
        partition by
            sec._dbt_source_relation,
            sec.sections_id,
            c.quarter,
            ge.assignment_category_code
        order by c.week_number_quarter asc
    ) as assignment_count_section_quarter_category_running_week,

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
    sec.terms_firstday >= '2024-07-01'
    -- and ge.region = 'Miami'
    -- and ge.school_level = 'MS'
    
