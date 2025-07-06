with
    sections as (
        select
            s._dbt_source_relation,
            s.sections_dcid,
            s.sections_id,
            s.sections_schoolid,
            s.sections_course_number,
            s.sections_section_number,
            s.sections_external_expression,
            s.courses_course_name,
            s.courses_credittype,
            s.courses_excludefromgpa,
            s.is_ap_course,
            s.teachernumber,
            s.teacher_lastfirst,
            s.terms_yearid,
            s.terms_firstday,
            s.terms_lastday,

        from {{ ref("base_powerschool__sections") }} as s
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on s.terms_academic_year = e1.academic_year
            and s.sections_course_number = e1.course_number
            and e1.view_name = 'gradebook_audit_section_week_scaffold'
            and e1.school_id is null
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on s.terms_academic_year = e2.academic_year
            and s.sections_schoolid = e2.school_id
            and s.sections_course_number = e2.course_number
            and e2.view_name = 'gradebook_audit_section_week_scaffold'
            and e2.school_id is not null
        where
            s.terms_academic_year = {{ var("current_academic_year") }}
            and e1.`include` is null
            and e2.`include` is null
    ),

    term_weeks as (
        select
            t._dbt_source_relation,
            t.schoolid,
            t.yearid,
            t.academic_year,
            t.term as `quarter`,
            t.semester,
            t.term_start_date as quarter_start_date,
            t.term_end_date as quarter_end_date,
            t.is_current_term,

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

            cast(t.academic_year as string)
            || '-'
            || right(cast(t.academic_year + 1 as string), 2) as academic_year_display,

            max(cw.week_end_date) over (
                partition by t._dbt_source_relation, t.schoolid, t.yearid, t.term
            ) as quarter_end_date_insession,

        from {{ ref("int_powerschool__terms") }} as t
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on t.schoolid = sch.school_number
            and {{ union_dataset_join_clause(left_alias="t", right_alias="sch") }}
        inner join
            {{ ref("int_powerschool__calendar_week") }} as cw
            on t.yearid = cw.yearid
            and t.schoolid = cw.schoolid
            and t.term = cw.quarter
            and {{ union_dataset_join_clause(left_alias="t", right_alias="cw") }}
        where
            t.academic_year = {{ var("current_academic_year") }}
            and t.term_start_date <= current_date('{{ var("local_timezone") }}')
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

    r.sam_account_name as teacher_tableau_username,

    leader.head_of_school_preferred_name_lastfirst as hos,
    leader.school_leader_preferred_name_lastfirst as school_leader,
    leader.school_leader_sam_account_name as school_leader_tableau_username,

    case
        -- when
        -- tw.region_school_level = 'MiamiES'
        -- and current_date(
        -- '{{ var("local_timezone") }}'
        -- ) between (tw.quarter_end_date_insession - interval 40 day) and (
        -- tw.quarter_end_date_insession + interval 14 day
        -- )
        -- then true
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
    {{ ref("int_people__leadership_crosswalk") }} as leader
    on tw.schoolid = leader.home_work_location_powerschool_school_id
