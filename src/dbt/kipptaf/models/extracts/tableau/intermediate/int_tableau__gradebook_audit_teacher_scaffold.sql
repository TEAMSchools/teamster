with
    sections as (
        select
            s._dbt_source_relation,
            s.terms_yearid,
            s.terms_firstday,
            s.terms_lastday,
            s.terms_academic_year as academic_year,
            s.sections_dcid,
            s.sections_id as sectionid,
            s.sections_schoolid as schoolid,
            s.sections_course_number as course_number,
            s.sections_section_number as section_number,
            s.sections_external_expression as external_expression,
            s.courses_course_name as course_name,
            s.courses_credittype as credit_type,
            s.courses_excludefromgpa as exclude_from_gpa,
            s.is_ap_course,
            s.teachernumber as teacher_number,
            s.teacher_lastfirst as teacher_name,

            r.sam_account_name as teacher_tableau_username,

        from {{ ref("base_powerschool__sections") }} as s
        left join
            {{ ref("int_people__staff_roster") }} as r
            on s.teachernumber = r.powerschool_teacher_number
        /* exceptions listed below completely remove a course/section/credit type from
           the entire gradebook audit dash, including from the gradebook categories
           view, for the entire school year */
        left join
            -- global on course_number
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on s.terms_academic_year = e1.academic_year
            and s.sections_course_number = e1.course_number
            and e1.view_name = 'teacher_scaffold'
            and e1.cte = 'sections'
            and e1.school_id is null
        left join
            -- course_number for certain schools only
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on s.terms_academic_year = e2.academic_year
            and s.sections_schoolid = e2.school_id
            and s.sections_course_number = e2.course_number
            and e2.view_name = 'teacher_scaffold'
            and e2.cte = 'sections'
            and e2.school_id is not null
        where
            s.terms_academic_year = {{ var("current_academic_year") - 1 }}
            and e1.include_row is null
            and e2.include_row is null
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

            l.head_of_school_preferred_name_lastfirst as hos,
            l.school_leader_preferred_name_lastfirst as school_leader,
            l.school_leader_sam_account_name as school_leader_tableau_username,

            concat(cw.region, cw.school_level) as region_school_level,

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
        left join
            {{ ref("int_people__leadership_crosswalk") }} as l
            on t.schoolid = l.home_work_location_powerschool_school_id
        where
            t.academic_year = {{ var("current_academic_year") - 1 }}
            -- and t.term_start_date <= current_date('{{ var("local_timezone") }}')
            and t.schoolid not in (0, 999999)
    ),

    final as (
        select
            tw.*,

            sec.sections_dcid,
            sec.sectionid,
            sec.section_number,
            sec.external_expression,
            sec.course_number,
            sec.course_name,
            sec.credit_type,
            sec.exclude_from_gpa,
            sec.is_ap_course,
            sec.teacher_number,
            sec.teacher_name,
            sec.teacher_tableau_username,

            null as assignment_category_code,
            null as assignment_category_name,
            null as assignment_category_term,
            null as expectation,
            null as notes,

            'teacher_scaffold' as scaffold_name,

            if(tw.`quarter` = 'Q4', true, false) as is_quarter_end_date_range,

            -- case
            -- when
            -- current_date(
            -- '{{ var("local_timezone") }}'
            -- ) between (tw.quarter_end_date_insession - interval 7 day) and (
            -- tw.quarter_end_date_insession + interval 14 day
            -- )
            -- then true
            -- else false
            -- end as is_quarter_end_date_range,
            if(
                tw.school_level = 'HS', sec.external_expression, sec.section_number
            ) as section_or_period,

        from term_weeks as tw
        inner join
            sections as sec
            on tw.schoolid = sec.schoolid
            and tw.yearid = sec.terms_yearid
            and tw.week_end_date between sec.terms_firstday and sec.terms_lastday
            and {{ union_dataset_join_clause(left_alias="tw", right_alias="sec") }}
        where sec.academic_year = {{ var("current_academic_year") - 1 }}

        union all

        select
            tw.*,

            sec.sections_dcid,
            sec.sectionid,
            sec.section_number,
            sec.external_expression,
            sec.course_number,
            sec.course_name,
            sec.credit_type,
            sec.exclude_from_gpa,
            sec.is_ap_course,
            sec.teacher_number,
            sec.teacher_name,
            sec.teacher_tableau_username,

            ge.assignment_category_code,
            ge.assignment_category_name,
            ge.assignment_category_term,
            ge.expectation,
            ge.notes,

            'teacher_category_scaffold' as scaffold_name,

            if(tw.`quarter` = 'Q4', true, false) as is_quarter_end_date_range,

            -- case
            -- when
            -- current_date(
            -- '{{ var("local_timezone") }}'
            -- ) between (tw.quarter_end_date_insession - interval 7 day) and (
            -- tw.quarter_end_date_insession + interval 14 day
            -- )
            -- then true
            -- else false
            -- end as is_quarter_end_date_range,
            if(
                tw.school_level = 'HS', sec.external_expression, sec.section_number
            ) as section_or_period,

        from term_weeks as tw
        inner join
            sections as sec
            on tw.schoolid = sec.schoolid
            and tw.yearid = sec.terms_yearid
            and tw.week_end_date between sec.terms_firstday and sec.terms_lastday
            and {{ union_dataset_join_clause(left_alias="tw", right_alias="sec") }}
        inner join
            {{ ref("stg_google_sheets__gradebook_expectations_assignments") }} as ge
            on tw.region = ge.region
            and tw.school_level = ge.school_level
            and tw.academic_year = ge.academic_year
            and tw.quarter = ge.quarter
            and tw.week_number_quarter = ge.week_number
        /* exceptions listed below completely remove rows for certain gradebook
           categories for a course/section/credit type from the entire gradebook audit
           dash, but NOT the entire course/section/credit type, for the entire sy */
        left join
            -- global by course_number
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on sec.academic_year = e1.academic_year
            and sec.course_number = e1.course_number
            and ge.assignment_category_code = e1.gradebook_category
            and e1.view_name = 'teacher_category_scaffold'
            and e1.cte = 'final'
        where e1.include_row is null
    )

select f.*,
from final as f
/* exceptions listed below completely remove rows from the entire gradebook audit
   dash, but only when EOQ is false. these rows will reappear when eoq starts */
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
    on f.academic_year = e1.academic_year
    and f.region = e1.region
    and f.school_level = e1.school_level
    and f.credit_type = e1.credit_type
    and f.is_quarter_end_date_range = e1.is_quarter_end_date_range
    and e1.view_name = 'teacher_scaffold'
    and e1.cte is null
-- permantently remove flags for certain categories for credit types
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
    on f.academic_year = e2.academic_year
    and f.region = e2.region
    and f.school_level = e2.school_level
    and f.credit_type = e2.credit_type
    and f.assignment_category_code = e2.gradebook_category
    and e2.view_name = 'teacher_category_scaffold'
    and e2.cte = 'final'
-- permantently remove flags for certain categories for courses
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e3
    on f.academic_year = e3.academic_year
    and f.region = e3.region
    and f.course_number = e3.course_number
    and f.assignment_category_code = e3.gradebook_category
    and e3.credit_type is null
    and e3.view_name = 'teacher_category_scaffold'
    and e3.cte = 'final'
where e1.include_row is null and e2.include_row is null and e3.include_row is null
