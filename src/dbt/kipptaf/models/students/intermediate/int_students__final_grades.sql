with
    -- One row. See int_students__sis_cutover for why the boundary is a floor
    -- and why it is derived from recorded attendance rather than row presence.
    sis_cutover as (
        select focus_start_academic_year, from {{ ref("int_students__sis_cutover") }}
    ),

    -- base_powerschool__final_grades carries studentid but no student_number,
    -- and the Focus branch has no PowerSchool studentid at all --
    -- int_students__student_enrollment_union leaves studentid and yearid null on
    -- all 10,075 Miami rows. student_number is the only student key both
    -- branches share, so it is resolved here and fct_grades_term joins
    -- enrollment on it. dcid >= 1 is the placeholder filter; the result is
    -- unique on (id, _dbt_source_project), so this join cannot fan out, and the
    -- swap is row-identical for all 3 NJ regions when measured against prod.
    powerschool_students as (
        select id as studentid, student_number, _dbt_source_project,
        from {{ ref("stg_powerschool__students") }}
        where dcid >= 1
    ),

    powerschool_conformed as (
        select
            fg._dbt_source_relation,
            fg._dbt_source_project,
            fg.cc_dcid,
            fg.studentid,
            fg.yearid,
            fg.schoolid,
            fg.academic_year,
            fg.storecode,
            fg.termbin_start_date,
            fg.termbin_end_date,
            fg.term_percent_grade,
            fg.term_letter_grade,
            fg.term_percent_grade_adjusted,
            fg.term_letter_grade_adjusted,
            fg.citizenship,
            fg.y1_percent_grade,
            fg.y1_percent_grade_adjusted,
            fg.y1_letter_grade,
            fg.y1_letter_grade_adjusted,
            fg.term_grade_points,
            fg.y1_grade_points,
            fg.potential_credit_hours,
            fg.lastgradeupdate,
            fg.exclude_from_gpa,

            ps.student_number,
        from {{ ref("base_powerschool__final_grades") }} as fg
        cross join sis_cutover as sc
        -- left, not inner: an inner join would silently drop any final-grade row
        -- whose student fails the dcid >= 1 placeholder filter, changing the NJ
        -- population. Measured at zero such rows, but the join type is what
        -- guarantees it stays that way.
        left join
            powerschool_students as ps
            on fg.studentid = ps.studentid
            and fg._dbt_source_project = ps._dbt_source_project
        where
            not (
                fg._dbt_source_project = 'kippmiami'
                and fg.academic_year >= sc.focus_start_academic_year
            )
    ),

    focus_conformed as (
        select
            g._dbt_source_relation,
            g._dbt_source_project,

            -- cc_dcid parity with int_students__course_enrollments, which maps
            -- Focus's student_schedule_id to cc_dcid. That is what makes
            -- fct_grades_term's student_section_enrollment_key resolve against
            -- dim_student_section_enrollments. Verified 1:1 against prod: all
            -- 1,593 AY2026 grade rows match exactly one schedule row, no
            -- orphans and no fan-out.
            sch.student_schedule_id as cc_dcid,

            g.academic_year,

            -- PowerSchool's yearid is academic_year - 1990. Deriving it keeps
            -- fct_grades_term's reporting-terms join working unchanged for both
            -- branches. Focus has no PowerSchool studentid, so that stays null.
            g.academic_year - 1990 as yearid,

            g.marking_period_short_name as storecode,
            g.marking_period_start_date as termbin_start_date,
            g.marking_period_end_date as termbin_end_date,

            g.grade_title as term_letter_grade,
            g.percent_grade as term_percent_grade,
            g.gpa_points as term_grade_points,

            st.student_number,
            loc.powerschool_school_id as schoolid,

            cast(null as int64) as studentid,

            -- Focus posts one grade per marking period with no adjusted variant
            -- and no year-to-date rollup, so these have no Focus analog. Null
            -- rather than copied from the term value: a YTD column that silently
            -- equals the term grade reads as a real rollup and is not one.
            cast(null as float64) as term_percent_grade_adjusted,
            cast(null as string) as term_letter_grade_adjusted,
            cast(null as float64) as y1_percent_grade,
            cast(null as float64) as y1_percent_grade_adjusted,
            cast(null as string) as y1_letter_grade,
            cast(null as string) as y1_letter_grade_adjusted,
            cast(null as float64) as y1_grade_points,

            -- Focus has no citizenship grade, and modified_date is null on every
            -- student_report_card_grades row, so there is no last-update stamp.
            cast(null as string) as citizenship,
            cast(null as date) as lastgradeupdate,

            safe_cast(g.credits as float64) as potential_credit_hours,

            -- PowerSchool stores the exclusion; Focus stores the inclusion.
            if(g.affects_gpa = 'Y', 0, 1) as exclude_from_gpa,

        from {{ ref("int_focus__report_card_grades") }} as g
        inner join
            {{ ref("int_focus__schedule") }} as sch
            on g.student_id = sch.student_id
            and g.course_period_id = sch.course_period_id
            and g.academic_year = sch.academic_year
        inner join
            {{ ref("int_focus__students") }} as st on g.student_id = st.student_id
        inner join {{ ref("int_focus__schools") }} as fs on g.schoolid = fs.id
        left join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on fs.school_number = loc.focus_school_id
        -- Imported course history predates the Focus cutover and overlaps the
        -- frozen PowerSchool archive for the years the archive covers. The
        -- archive branch above already owns those years, so admit only rows at
        -- or after the cutover -- the same boundary, applied from the other side.
        cross join sis_cutover as sc
        where g.academic_year >= sc.focus_start_academic_year
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
