with
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
            fg.comment_value,

            fg.students_student_number as student_number,
        from {{ ref("base_powerschool__final_grades") }} as fg
    ),

    focus_posted_grades as (
        -- grain projection, not dup-masking
        select distinct
            _dbt_source_project,
            student_id,
            course_period_id,
            marking_period_id,

            'DT' as superseded_grade_type_token,
        from {{ ref("int_focus__report_card_grades") }}
        where grade_type_token is null and course_period_id is not null
    ),

    focus_conformed as (
        select
            g._dbt_source_relation,
            g._dbt_source_project,

            -- cc_dcid parity with int_students__course_enrollments, which maps
            -- Focus's student_schedule_id to cc_dcid.
            sch.student_schedule_id as cc_dcid,

            g.academic_year,

            g.marking_period_short_name as storecode,
            g.marking_period_start_date as termbin_start_date,
            g.marking_period_end_date as termbin_end_date,

            g.grade_title as term_letter_grade,
            g.percent_grade as term_percent_grade,
            g.gpa_points as term_grade_points,

            st.student_number,
            loc.powerschool_school_id as schoolid,

            -- PowerSchool's yearid is academic_year - 1990. Deriving it keeps
            -- fct_grades_term's reporting-terms join working for both branches.
            g.academic_year - 1990 as yearid,

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
            cast(null as string) as comment_value,

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
        left join
            focus_posted_grades as pg
            on g._dbt_source_project = pg._dbt_source_project
            and g.student_id = pg.student_id
            and g.course_period_id = pg.course_period_id
            and g.marking_period_id = pg.marking_period_id
            and g.grade_type_token = pg.superseded_grade_type_token
        -- Imported course history predates the Focus cutover and overlaps the
        -- frozen PowerSchool archive for the years the archive covers. The
        -- archive branch above already owns those years, so admit only rows at
        -- or after the cutover — the same boundary, applied from the other
        -- side. Course history also carries an invariant the schedule join
        -- depends on: every row has a null `course_period_id` (15,278 of
        -- 15,278) and drops out of that inner join anyway.
        where
            g.academic_year >= 2026
            and pg.student_id is null
            -- E rows are exam grades, not term grades; they collide with the
            -- posted grade on this model's grain
            and g.grade_type_token is distinct from 'E'
    )

select
    _dbt_source_relation,
    _dbt_source_project,
    cc_dcid,
    studentid,
    yearid,
    schoolid,
    academic_year,
    storecode,
    termbin_start_date,
    termbin_end_date,
    term_percent_grade,
    term_letter_grade,
    term_percent_grade_adjusted,
    term_letter_grade_adjusted,
    citizenship,
    y1_percent_grade,
    y1_percent_grade_adjusted,
    y1_letter_grade,
    y1_letter_grade_adjusted,
    term_grade_points,
    y1_grade_points,
    potential_credit_hours,
    lastgradeupdate,
    exclude_from_gpa,
    student_number,
    comment_value,
from powerschool_conformed

union all

select
    _dbt_source_relation,
    _dbt_source_project,
    cc_dcid,
    studentid,
    yearid,
    schoolid,
    academic_year,
    storecode,
    termbin_start_date,
    termbin_end_date,
    term_percent_grade,
    term_letter_grade,
    term_percent_grade_adjusted,
    term_letter_grade_adjusted,
    citizenship,
    y1_percent_grade,
    y1_percent_grade_adjusted,
    y1_letter_grade,
    y1_letter_grade_adjusted,
    term_grade_points,
    y1_grade_points,
    potential_credit_hours,
    lastgradeupdate,
    exclude_from_gpa,
    student_number,
    comment_value,
from focus_conformed
