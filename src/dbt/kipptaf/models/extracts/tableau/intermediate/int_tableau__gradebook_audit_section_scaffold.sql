{{- config(materialized="table") -}}

with
    sections as (
        select
            _dbt_source_relation,
            sections_dcid,
            sections_id,
            sections_schoolid,
            sections_course_number,
            teachernumber,
            terms_yearid,
            terms_firstday,
            terms_lastday,
        from {{ ref("base_powerschool__sections") }}
        where
            /* exclude courses */
            courses_course_number not in (
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
            and concat(sections_course_number, sections_schoolid) not in (
                'GYM08035G1732514',
                'GYM08036G2732514',
                'GYM08037G3732514',
                'GYM08038G4732514',
                'SEM72250G1133570965',
                'SEM72250G173252',
                'SEM72250G2133570965',
                'SEM72250G273252',
                'SEM72250G3133570965',
                'SEM72250G373252',
                'SEM72250G4133570965',
                'SEM72250G473252'
            )
    )

select
    t._dbt_source_relation,
    t.schoolid,
    t.yearid,
    t.academic_year,

    tb.storecode as `quarter`,
    tb.semester,
    tb.date1 as quarter_start_date,
    tb.date2 as quarter_end_date,
    tb.is_current_term,
    tb.is_quarter_end_date_range,

    cw.region,
    cw.school_level,
    cw.week_start_date,
    cw.week_end_date,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.school_week_start_date_lead,
    cw.week_number_academic_year,
    cw.week_number_quarter,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    sec.sections_dcid,
    sec.sections_id as sectionid,
    sec.teachernumber as teacher_number,

    r.sam_account_name as tableau_username,
from {{ ref("stg_powerschool__terms") }} as t
inner join
    {{ ref("stg_powerschool__termbins") }} as tb
    on t.schoolid = tb.schoolid
    and t.id = tb.termid
    and {{ union_dataset_join_clause(left_alias="t", right_alias="tb") }}
    and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
    and tb.date1 <= current_date('{{ var("local_timezone") }}')
inner join
    {{ ref("int_powerschool__calendar_week") }} as cw
    on t.yearid = cw.yearid
    and t.schoolid = cw.schoolid
    and {{ union_dataset_join_clause(left_alias="t", right_alias="cw") }}
inner join
    {{ ref("stg_reporting__gradebook_expectations") }} as ge
    on cw.region = ge.region
    and cw.school_level = ge.school_level
    and cw.academic_year = ge.academic_year
    and cw.quarter = ge.quarter
    and cw.week_number_quarter = ge.week_number
inner join
    sections as sec
    on cw.schoolid = sec.sections_schoolid
    and cw.yearid = sec.terms_yearid
    and cw.week_end_date between sec.terms_firstday and sec.terms_lastday
    and {{ union_dataset_join_clause(left_alias="cw", right_alias="sec") }}
left join
    {{ ref("base_people__staff_roster") }} as r
    on sec.teachernumber = r.powerschool_teacher_number
where
    t.yearid = {{ var("current_academic_year") - 1990 }}
    and t.isyearrec = 1
    and t.schoolid not in (0, 999999)
    /* exclude F & S categories for iReady courses */
    and concat(sec.sections_course_number, ge.assignment_category_code) not in (
        'SEM72005G1F',
        'SEM72005G2F',
        'SEM72005G3F',
        'SEM72005G4F',
        'SEM72005G1S',
        'SEM72005G2S',
        'SEM72005G3S',
        'SEM72005G4S'
    )
