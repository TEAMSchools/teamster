with
    sections as (
        select
            _dbt_source_relation,
            sections_dcid,
            sections_id,
            sections_schoolid,
            sections_course_number,
            sections_section_number,
            sections_external_expression,
            courses_course_name,
            courses_credittype,
            courses_excludefromgpa,
            is_ap_course,
            teachernumber,
            teacher_lastfirst,
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
                'SEM72250G473252',
                'HR30200803,'
            )
    ),

    term_weeks as (
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

            sch.abbreviation as school,

            cw.region,
            cw.school_level,
            cw.week_start_date,
            cw.week_end_date,
            cw.week_start_monday,
            cw.week_end_sunday,
            cw.school_week_start_date_lead,
            cw.week_number_academic_year,
            cw.week_number_quarter,

            concat(cw.region, cw.school_level) as region_school_level,

            cast(t.academic_year as string)
            || '-'
            || right(cast(t.academic_year + 1 as string), 2) as academic_year_display,

            max(cw.week_end_date) over (
                partition by t._dbt_source_relation, t.schoolid, t.yearid, tb.storecode
            ) as quarter_end_date_insession,

        from {{ ref("stg_powerschool__terms") }} as t
        inner join
            {{ ref("stg_powerschool__termbins") }} as tb
            on t.schoolid = tb.schoolid
            and t.id = tb.termid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="tb") }}
            and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
            and tb.date1 <= current_date('{{ var("local_timezone") }}')
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on t.schoolid = sch.school_number
            and {{ union_dataset_join_clause(left_alias="t", right_alias="sch") }}
        inner join
            {{ ref("int_powerschool__calendar_week") }} as cw
            on t.yearid = cw.yearid
            and t.schoolid = cw.schoolid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="cw") }}
            and tb.storecode = cw.quarter
            and {{ union_dataset_join_clause(left_alias="tb", right_alias="cw") }}
        where
            t.yearid = {{ var("current_academic_year") - 1990 }}
            and t.isyearrec = 1
            and t.schoolid not in (0, 999999)
    )

select
    tw.*,

    sec.sections_dcid,
    sec.sections_id as sectionid,
    sec.sections_section_number as section_number,
    sec.sections_external_expression as external_expression,
    sec.sections_course_number as course_number,
    sec.courses_course_name as course_name,
    sec.courses_credittype as credit_type,
    sec.courses_excludefromgpa as exclude_from_gpa,
    sec.is_ap_course,
    sec.teachernumber as teacher_number,
    sec.teacher_lastfirst as teacher_name,

    r.sam_account_name as tableau_username,

    hos.head_of_school_preferred_name_lastfirst as hos,

    concat(
        tw.region_school_level, sec.courses_credittype
    ) as region_school_level_credit_type,

    case
        when
            tw.region_school_level = 'MiamiES'
            and current_date(
                '{{ var("local_timezone") }}'
            ) between (tw.quarter_end_date_insession - interval 40 day) and (
                tw.quarter_end_date_insession + interval 14 day
            )
        then true
        when
            current_date(
                '{{ var("local_timezone") }}'
            ) between (tw.quarter_end_date_insession - interval 7 day) and (
                tw.quarter_end_date_insession + interval 14 day
            )
        then true
        else false
    end as is_quarter_end_date_range,

    if(
        tw.school_level = 'HS',
        sec.sections_external_expression,
        sec.sections_section_number
    ) as section_or_period,

from term_weeks as tw
inner join
    sections as sec
    on tw.schoolid = sec.sections_schoolid
    and tw.yearid = sec.terms_yearid
    and tw.week_end_date between sec.terms_firstday and sec.terms_lastday
    and {{ union_dataset_join_clause(left_alias="tw", right_alias="sec") }}
left join
    {{ ref("int_people__staff_roster") }} as r
    on sec.teachernumber = r.powerschool_teacher_number
left join
    {{ ref("int_people__leadership_crosswalk") }} as hos
    on tw.schoolid = hos.home_work_location_powerschool_school_id
where concat(tw.region_school_level, sec.courses_credittype) != 'MiamiESSOC'
