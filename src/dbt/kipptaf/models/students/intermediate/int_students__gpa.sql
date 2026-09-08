with
    -- One row. See int_students__sis_cutover for why the boundary is a floor
    -- and why it is derived from recorded attendance rather than row presence.
    sis_cutover as (
        select
            focus_start_academic_year,

            -- PowerSchool yearid form of the same boundary, so the archive
            -- branch filters on a bare gt.yearid instead of recomputing
            -- yearid + 1990 per row in WHERE.
            focus_start_academic_year - 1990 as focus_start_yearid,
        from {{ ref("int_students__sis_cutover") }}
    ),

    -- dcid >= 1 is the placeholder filter. See the model description for why
    -- student_number is the join key.
    powerschool_students as (
        select id as studentid, student_number, _dbt_source_project,
        from {{ ref("stg_powerschool__students") }}
        where dcid >= 1
    ),

    powerschool_conformed as (
        select
            gt._dbt_source_relation,
            gt._dbt_source_project,
            gt.studentid,
            gt.schoolid,
            gt.yearid,
            gt.term_name,
            gt.semester,
            gt.gpa_term,
            gt.gpa_y1,
            gt.gpa_y1_unweighted,
            gt.gpa_semester,
            gt.n_failing_y1,
            gt.total_credit_hours_term,
            gt.total_credit_hours_y1,
            gt.grade_avg_term,
            gt.grade_avg_y1,

            gc.cumulative_y1_gpa,
            gc.cumulative_y1_gpa_unweighted,
            gc.cumulative_y1_gpa_projected,
            gc.earned_credits_cum,
            gc.potential_credits_cum,

            ps.student_number,

            -- PowerSchool's yearid is academic_year - 1990. gpa_term carries no
            -- academic_year of its own, and the Focus branch has no yearid, so
            -- both columns are derived on whichever side lacks them.
            gt.yearid + 1990 as academic_year,

            -- The PowerSchool GPA chain does not produce class rank at all.
            cast(null as int64) as class_rank,
        from {{ ref("int_powerschool__gpa_term") }} as gt
        cross join sis_cutover as sc
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on gt.studentid = gc.studentid
            and gt.schoolid = gc.schoolid
            and gt._dbt_source_project = gc._dbt_source_project
        -- left, not inner: an inner join would silently drop any GPA row whose
        -- student fails the dcid >= 1 placeholder filter, changing the NJ
        -- population. Measured at zero such rows, but the join type is what
        -- guarantees it stays that way.
        left join
            powerschool_students as ps
            on gt.studentid = ps.studentid
            and gt._dbt_source_project = ps._dbt_source_project
        where
            not (
                gt._dbt_source_project = 'kippmiami'
                and gt.yearid >= sc.focus_start_yearid
            )
    ),

    focus_conformed as (
        select
            g._dbt_source_relation,
            g._dbt_source_project,

            g.syear as academic_year,

            g.class_rank,

            st.student_number,
            loc.powerschool_school_id as schoolid,

            -- Derived so the reporting-terms join in fct_grades_gpa keeps
            -- working for both branches, even though no Focus row resolves a
            -- term.
            g.syear - 1990 as yearid,

            cast(null as int64) as studentid,

            -- Focus's student_gpa_calculated is course-history GPA only: every
            -- row carries marking_period_id = -1 and there is no term-grained
            -- row in the table. So no term, semester or year-to-date measure has
            -- a Focus analog. Null rather than copied from the cumulative value:
            -- a term GPA that silently equals the cumulative one reads as a real
            -- term measure and is not one.
            cast(null as string) as term_name,
            cast(null as string) as semester,
            cast(null as float64) as gpa_term,
            cast(null as float64) as gpa_y1,
            cast(null as float64) as gpa_y1_unweighted,
            cast(null as float64) as gpa_semester,
            cast(null as int64) as n_failing_y1,
            cast(null as float64) as total_credit_hours_term,
            cast(null as float64) as total_credit_hours_y1,
            cast(null as float64) as grade_avg_term,
            cast(null as float64) as grade_avg_y1,

            -- PowerSchool's cumulative_y1_gpa is the weighted measure and
            -- cumulative_y1_gpa_unweighted the unweighted one, so the two Focus
            -- columns map across that way round rather than by name.
            cast(g.cumulative_weighted_gpa as float64) as cumulative_y1_gpa,
            cast(g.cumulative_gpa as float64) as cumulative_y1_gpa_unweighted,
            cast(g.cumulative_credits as float64) as earned_credits_cum,

            -- Focus projects neither a year-end GPA nor potential credits.
            cast(null as float64) as cumulative_y1_gpa_projected,
            cast(null as float64) as potential_credits_cum,

        from {{ ref("stg_focus__student_gpa_calculated") }} as g
        inner join
            {{ ref("int_focus__students") }} as st on g.student_id = st.student_id
        inner join {{ ref("int_focus__schools") }} as fs on g.school_id = fs.id
        left join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on fs.school_number = loc.focus_school_id
        -- The archive branch above owns Miami's years before the cutover, so
        -- admit only rows at or after it — the same boundary, applied from the
        -- other side.
        cross join sis_cutover as sc
        where g.syear >= sc.focus_start_academic_year
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
