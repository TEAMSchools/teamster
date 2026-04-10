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

            if(
                s.school_name = 'KIPP Sumner Elementary' and s.sections_grade_level = 5,
                'MS',
                null
            ) as school_level_alt,

        from {{ ref("base_powerschool__sections") }} as s
        left join
            {{ ref("int_people__staff_roster") }} as r
            on s.teachernumber = r.powerschool_teacher_number
        left join
            /* permanently remove rows from the gradebook audit dash based on course
            number */
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on s.terms_academic_year = e1.academic_year
            and s.sections_course_number = e1.course_number
            and e1.view_name = 'teacher_scaffold'
            and e1.cte = 'sections'
            and e1.school_id is null
        left join
            /* permanently remove rows from the gradebook audit dash based on course
            number for certain schools only */
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on s.terms_academic_year = e2.academic_year
            and s.sections_schoolid = e2.school_id
            and s.sections_course_number = e2.course_number
            and e2.view_name = 'teacher_scaffold'
            and e2.cte = 'sections'
            and e2.school_id is not null
        where
            s.terms_academic_year = {{ var("current_academic_year") }}
            and s.sections_no_of_students != 0
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
            t.academic_year = {{ var("current_academic_year") }}
            and t.term_start_date <= current_date('{{ var("local_timezone") }}')
            and t.schoolid not in (0, 999999)
    ),

    school_level_mod as (
        select
            tw._dbt_source_relation,
            tw.schoolid,
            tw.yearid,
            tw.academic_year,
            tw.`quarter`,
            tw.semester,
            tw.quarter_start_date,
            tw.quarter_end_date,
            tw.is_current_term,
            tw.school,
            tw.region,
            tw.week_start_date,
            tw.week_end_date,
            tw.week_start_monday,
            tw.week_end_sunday,
            tw.school_week_start_date_lead,
            tw.week_number_academic_year,
            tw.week_number_quarter,
            tw.hos,
            tw.school_leader,
            tw.school_leader_tableau_username,

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

            concat(
                tw.region, coalesce(sec.school_level_alt, tw.school_level)
            ) as region_school_level,

            coalesce(sec.school_level_alt, tw.school_level) as school_level,

            case
                when
                    tw.region = 'Miami'
                    and current_date(
                        '{{ var("local_timezone") }}'
                    ) between (tw.quarter_end_date_insession - interval 9 day) and (
                        tw.quarter_end_date_insession + interval 28 day
                    )
                then true
                when
                    tw.school_level = 'HS'
                    and tw.`quarter` = 'Q3'
                    and current_date(
                        '{{ var("local_timezone") }}'
                    ) between (tw.quarter_end_date_insession + interval 9 day) and (
                        tw.quarter_end_date_insession + interval 20 day
                    )
                then true
                when tw.school_level = 'HS' and tw.`quarter` = 'Q3'
                then false
                when
                    tw.region != 'Miami'
                    and current_date(
                        '{{ var("local_timezone") }}'
                    ) between (tw.quarter_end_date_insession - interval 5 day) and (
                        tw.quarter_end_date_insession + interval 14 day
                    )
                then true
                else false
            end as is_quarter_end_date_range,

            if(
                tw.school_level = 'HS', sec.external_expression, sec.section_number
            ) as section_or_period,

            max(tw.week_end_date) over (
                partition by
                    tw._dbt_source_relation, tw.schoolid, tw.yearid, tw.`quarter`
            ) as quarter_end_date_insession,

        from term_weeks as tw
        inner join
            sections as sec
            on tw.schoolid = sec.schoolid
            and tw.yearid = sec.terms_yearid
            and tw.week_end_date between sec.terms_firstday and sec.terms_lastday
            and {{ union_dataset_join_clause(left_alias="tw", right_alias="sec") }}
        where sec.academic_year = {{ var("current_academic_year") }}
    )

select
    slm.*,

    ge.assignment_category_code,
    ge.assignment_category_name,
    ge.assignment_category_term,
    ge.expectation,
    ge.notes,

    if(
        current_date('{{ var("local_timezone") }}')
        between slm.week_start_monday and slm.week_end_sunday,
        true,
        false
    ) as is_current_week,

from school_level_mod as slm
inner join
    {{ ref("stg_google_sheets__gradebook_expectations_assignments") }} as ge
    on slm.region = ge.region
    and slm.school_level = ge.school_level
    and slm.academic_year = ge.academic_year
    and slm.quarter = ge.quarter
    and slm.week_number_quarter = ge.week_number
/* permanently remove rows for certain gradebook category(s) from the entire
   gradebook audit dash by course_number */
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
    on slm.academic_year = e1.academic_year
    and slm.course_number = e1.course_number
    and ge.assignment_category_code = e1.gradebook_category
    and e1.view_name = 'teacher_category_scaffold'
    and e1.cte = 'final'
/* permanently remove rows for certain gradebook category(s) from the entire
   gradebook audit dash by course_number for a region */
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
    on slm.academic_year = e2.academic_year
    and slm.course_number = e2.course_number
    and slm.region = e2.region
    and ge.assignment_category_code = e2.gradebook_category
    and e2.view_name = 'teacher_category_scaffold'
    and e2.cte = 'final'
/* permanently remove rows for certain gradebook category(s) from the entire
   gradebook audit dash by credit type for a region/school level */
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e3
    on slm.academic_year = e3.academic_year
    and slm.credit_type = e3.credit_type
    and slm.region = e3.region
    and slm.school_level = e3.school_level
    and ge.assignment_category_code = e3.gradebook_category
    and e3.view_name = 'teacher_category_scaffold'
    and e3.cte = 'final'
where e1.include_row is null and e2.include_row is null and e3.include_row is null
