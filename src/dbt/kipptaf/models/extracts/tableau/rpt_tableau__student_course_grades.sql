with
    term as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            schoolid,
            yearid,

            term as `quarter`,

            term_start_date as quarter_start_date,
            term_end_date as quarter_end_date,

            is_current_term as is_current_quarter,
            semester,

            case
                term when 'Q2' then 'Q1' when 'Q3' then 'Q2' when 'Q4' then 'Q3'
            end as prior_quarter,

        from {{ ref("int_students__terms") }}
        where term is not null

        union all

        select
            _dbt_source_relation,
            _dbt_source_project,
            schoolid,
            yearid,

            'Y1' as `quarter`,

            firstday as quarter_start_date,
            lastday as quarter_end_date,

            false as is_current_quarter,
            'S#' as semester,

            cast(null as string) as prior_quarter,

        from {{ ref("int_students__terms") }}
        where isyearrec = 1
    ),

    prior_year_gpa_rollup as (
        /* prior-year FINAL Y1 GPA — PowerSchool stores only end-of-year Y1
           grades, so a true as-of-same-quarter value does not exist (#4382).
           is_current picks the single Q4 row per school; the credit-hour
           weighted sum blends multi-school years down to student grain */
        select
            studentid,
            _dbt_source_project,

            count(*) as n_school_rows,
            max(gpa_y1) as gpa_y1_single_school,

            round(
                safe_divide(sum(weighted_gpa_points_y1), sum(total_credit_hours_y1)), 2
            ) as gpa_y1_blended,
        from {{ ref("int_powerschool__gpa_term") }}
        where yearid = {{ var("current_academic_year") - 1991 }} and is_current
        group by studentid, _dbt_source_project
    ),

    prior_year_gpa as (
        /* single-school years use the stored gpa_y1 verbatim — the blend's
           pre-rounded inputs drift +/-0.01 vs the exact value */
        select
            studentid,
            _dbt_source_project,

            if(
                n_school_rows = 1, gpa_y1_single_school, gpa_y1_blended
            ) as gpa_y1_prior_year,
        from prior_year_gpa_rollup
    ),

    prior_year_cumulative as (
        /* prior-year FINAL unweighted cumulative GPA — the baseline the
           in-progress projection is measured against. is_projected is true only
           for the year in progress, so filtering it out yields the actual
           end-of-year value rather than a projection of it.

           Upstream accumulates per student-school and its uniqueness key is
           (studentid, schoolid, academic_year), so a student at two schools in
           one year legitimately produces two rows and would fan this CTE out.
           AY2023 onward has none; AY2019-AY2022 had 11-29 a year, values
           genuinely differing. A recurrence would NOT fail CI — this model's
           own key test is severity warn for the unrelated #3915 storedgrades
           issue, so it would only inflate that warn count. Compare the count
           against prod rather than trusting a green build.

           That same per-school accumulation splits the middle- and high-school
           series, so a grade 9 row pairs a high-school projection with a
           middle-school baseline. See the column descriptions. */
        select
            studentid,
            _dbt_source_project,

            cumulative_y1_gpa_unweighted as cumulative_y1_gpa_unweighted_prior_year,
        from {{ ref("int_powerschool__gpa_cumulative_year") }}
        where
            academic_year = {{ var("current_academic_year") - 1 }} and not is_projected
    ),

    backfill_running_gpa as (
        /* TODO(#4687): TEMPORARY. Delete this CTE, its join in student_roster,
           and the coalesce on gpa_y1 once the dashboard runs on current-year
           data. Tracked in Asana under GPA and Gradebook Dashboard v3, Phase 4.

           Running credit-weighted GPA through each term, accumulated from the
           same components the real gpa_y1 uses. Deliberately NOT anchored to
           the stored Y1: the reconstruction reads 45.1, 46.7, 46.6, 48.2
           percent of high school students at or above 3.0 through Q1-Q4
           (AY2025) against a stored Y1 of 48.9 — it sits slightly below
           the stored value throughout, and anchoring Q4 to that value
           would introduce a discontinuity there rather than let the
           series read as one continuous trend. */
        select
            studentid,
            schoolid,
            yearid,
            _dbt_source_project,
            term_name,

            round(
                safe_divide(
                    sum(weighted_gpa_points_term) over (
                        partition by studentid, _dbt_source_project, schoolid, yearid
                        order by term_name
                    ),
                    sum(total_credit_hours_term) over (
                        partition by studentid, _dbt_source_project, schoolid, yearid
                        order by term_name
                    )
                ),
                2
            ) as gpa_y1_running,
        from {{ ref("int_powerschool__gpa_term") }}
        where yearid = {{ var("current_academic_year") - 1991 }}
    ),

    student_roster as (
        select
            enr._dbt_source_relation,
            enr._dbt_source_project,
            enr.studentid,
            enr.student_number,
            enr.student_name,
            enr.enroll_status,
            enr.cohort,
            enr.graduation_year,
            enr.gender,
            enr.ethnicity,
            enr.academic_year,
            enr.academic_year_display,
            enr.yearid,
            enr.region,
            enr.school_level_alt as school_level,
            enr.schoolid,
            enr.school,
            enr.grade_level,
            enr.advisory,
            enr.year_in_school,
            enr.year_in_network,
            enr.rn_undergrad,
            enr.is_self_contained as is_pathways,
            enr.is_out_of_district,
            enr.is_retained_year,
            enr.is_retained_ever,
            enr.student_slideback,
            enr.lunch_status,
            enr.lep_status,
            enr.gifted_and_talented,
            enr.iep_status,
            enr.is_504,
            enr.salesforce_id,
            enr.ktc_cohort,
            enr.is_counseling_services,
            enr.is_student_athlete,
            enr.ada,
            enr.unweighted_ada,
            enr.weighted_ada,
            enr.ada_above_or_at_80,
            enr.hos,
            enr.school_leader,
            enr.school_leader_tableau_username,

            term.quarter,
            term.quarter_start_date,
            term.quarter_end_date,
            term.is_current_quarter,
            term.semester,

            gtq.gpa_semester,
            gtq.total_credit_hours_y1 as gpa_total_credit_hours,

            gc.cumulative_y1_gpa,
            gc.cumulative_y1_gpa_unweighted,
            gc.cumulative_y1_gpa_projected,
            gc.cumulative_y1_gpa_projected_unweighted,
            gc.cumulative_y1_gpa_projected_s1,
            gc.cumulative_y1_gpa_projected_s1_unweighted,
            gc.core_cumulative_y1_gpa,
            gc.potential_gpa_credits_cum_projected,
            gc.potential_gpa_credits_current_year,
            gc.gpa_needed_for_cumulative_3_0,
            gc.is_cumulative_3_0_attainable,

            lb.gpa_y1_1_week_prior,
            lb.gpa_y1_2_week_prior,
            lb.gpa_y1_4_week_prior,
            lb.gpa_y1_unweighted_1_week_prior,
            lb.gpa_y1_unweighted_2_week_prior,
            lb.gpa_y1_unweighted_4_week_prior,
            lb.n_failing_y1_1_week_prior,
            lb.n_failing_y1_2_week_prior,
            lb.n_failing_y1_4_week_prior,

            gpq.gpa_y1 as gpa_y1_prior_quarter,
            gpq.n_failing_y1 as n_failing_y1_prior_quarter,

            pyg.gpa_y1_prior_year,

            pyc.cumulative_y1_gpa_unweighted_prior_year,

            enr.academic_year
            = {{ var("current_academic_year") }} as is_current_academic_year,

            if(
                term.quarter = 'Y1', gty.gpa_y1_unweighted, gtq.gpa_y1_unweighted
            ) as gpa_y1_unweighted,

            if(term.quarter = 'Y1', gty.gpa_y1, gtq.gpa_term) as gpa_for_quarter,

            coalesce(
                bfg.gpa_y1_running, if(term.quarter = 'Y1', gty.gpa_y1, gtq.gpa_y1)
            ) as gpa_y1,

            if(
                term.quarter = 'Y1', gty.n_failing_y1, gtq.n_failing_y1
            ) as gpa_n_failing_y1,

            /* KIPP GPA Band, the KIPP Foundation five-band unweighted scale
               documented in models/students/CLAUDE.md. Band 5 is open-ended
               rather than capped at the documented 4.00 because unweighted GPA
               reaches 4.33 and a closed upper bound leaves those rows unbanded.
               The trailing is-not-null arm keeps a null GPA out of band 1. */
            case
                when gc.cumulative_y1_gpa_projected_unweighted >= 3.50
                then 5
                when gc.cumulative_y1_gpa_projected_unweighted >= 3.00
                then 4
                when gc.cumulative_y1_gpa_projected_unweighted >= 2.50
                then 3
                when gc.cumulative_y1_gpa_projected_unweighted >= 2.00
                then 2
                when gc.cumulative_y1_gpa_projected_unweighted is not null
                then 1
            end as gpa_band_projected_unweighted,

            case
                when pyc.cumulative_y1_gpa_unweighted_prior_year >= 3.50
                then 5
                when pyc.cumulative_y1_gpa_unweighted_prior_year >= 3.00
                then 4
                when pyc.cumulative_y1_gpa_unweighted_prior_year >= 2.50
                then 3
                when pyc.cumulative_y1_gpa_unweighted_prior_year >= 2.00
                then 2
                when pyc.cumulative_y1_gpa_unweighted_prior_year is not null
                then 1
            end as gpa_band_unweighted_prior_year,

        from {{ ref("int_extracts__student_enrollments") }} as enr
        inner join
            term
            on enr.schoolid = term.schoolid
            and enr.yearid = term.yearid
            and enr._dbt_source_project = term._dbt_source_project
        left join
            {{ ref("int_powerschool__gpa_term") }} as gtq
            on enr.studentid = gtq.studentid
            and enr.yearid = gtq.yearid
            and enr.schoolid = gtq.schoolid
            and enr._dbt_source_project = gtq._dbt_source_project
            and term.quarter = gtq.term_name
            and term._dbt_source_project = gtq._dbt_source_project
        /* bfg is gated to the prior year in ON — the inverse of gc/lb/gpq/pyc's
           current-year gate below — so current-year rows get NULL here and
           the coalesce on gpa_y1 falls through to the untouched original
           expression */
        left join
            backfill_running_gpa as bfg
            on enr.studentid = bfg.studentid
            and enr.yearid = bfg.yearid
            and enr.schoolid = bfg.schoolid
            and enr._dbt_source_project = bfg._dbt_source_project
            and term.quarter = bfg.term_name
            and enr.academic_year = {{ var("current_academic_year") - 1 }}
        left join
            {{ ref("int_powerschool__gpa_term") }} as gty
            on enr.studentid = gty.studentid
            and enr.yearid = gty.yearid
            and enr.schoolid = gty.schoolid
            and enr._dbt_source_project = gty._dbt_source_project
            and gty.is_current
        /* gc join gated to the current year in ON: prior-year rows keep NULL
           cumulative/needed columns (as-of-today measures) */
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on enr.studentid = gc.studentid
            and enr.schoolid = gc.schoolid
            and enr._dbt_source_project = gc._dbt_source_project
            and enr.academic_year = {{ var("current_academic_year") }}
        /* lookback is current-year only by construction (yearid in the join
           key), so prior-year rows read NULL naturally */
        left join
            {{ ref("int_powerschool__gpa_term_lookback") }} as lb
            on enr.studentid = lb.studentid
            and enr.schoolid = lb.schoolid
            and enr.yearid = lb.yearid
            and enr._dbt_source_project = lb._dbt_source_project
        /* both comparison joins are current-year-only (as-of columns), gated
           in ON so prior-year rows keep NULLs */
        left join
            {{ ref("int_powerschool__gpa_term") }} as gpq
            on enr.studentid = gpq.studentid
            and enr.yearid = gpq.yearid
            and enr.schoolid = gpq.schoolid
            and enr._dbt_source_project = gpq._dbt_source_project
            and term.prior_quarter = gpq.term_name
            and enr.academic_year = {{ var("current_academic_year") }}
        left join
            prior_year_gpa as pyg
            on enr.studentid = pyg.studentid
            and enr._dbt_source_project = pyg._dbt_source_project
            and enr.academic_year = {{ var("current_academic_year") }}
        /* gated to the current year in ON, matching gc — the projection it is
           compared against is a current-year-only measure, so a prior-year row
           would carry a baseline with nothing to measure it against */
        left join
            prior_year_cumulative as pyc
            on enr.studentid = pyc.studentid
            and enr._dbt_source_project = pyc._dbt_source_project
            and enr.academic_year = {{ var("current_academic_year") }}
        where
            enr.rn_year = 1
            and not enr.is_out_of_district
            /* status guard drops pre-registered (-1, which can pass
               is_enrolled_recent) and invalid (1) rows */
            and enr.enroll_status in (0, 2, 3)
            and enr.is_enrolled_recent
            /* upper bound keeps next-year pre-enrollment stubs out of the
               2-year window */
            and enr.academic_year >= {{ var("current_academic_year") - 1 }}
            and enr.academic_year <= {{ var("current_academic_year") }}
            /* Miami hard-excluded: region unsupported in the rebuilt
               dashboard (#4340) */
            and enr.region in ('Newark', 'Camden', 'Paterson')
    ),

    course_enrollments as (
        select
            m._dbt_source_relation,
            m._dbt_source_project,
            m.cc_studentid as studentid,
            m.cc_yearid as yearid,
            m.cc_course_number as course_number,
            m.cc_sectionid as sectionid,
            m.cc_dateenrolled as date_enrolled,
            m.sections_dcid,
            m.sections_section_number as section_number,
            m.sections_external_expression as external_expression,
            m.courses_credittype as credit_type,
            m.courses_course_name as course_name,
            m.courses_excludefromgpa as exclude_from_gpa,
            m.teachernumber as teacher_number,
            m.teacher_lastfirst as teacher_name,

            f.is_tutoring as tutoring_nj,
            f.nj_student_tier,

            r.sam_account_name as teacher_tableau_username,
            r.reports_to_formatted_name as manager,
            r.reports_to_sam_account_name as report_to_sam_account_name,
        from {{ ref("base_powerschool__course_enrollments") }} as m
        left join
            {{ ref("int_extracts__student_enrollments_subjects") }} as f
            on m.cc_studentid = f.studentid
            and m.cc_academic_year = f.academic_year
            and m.courses_credittype = f.powerschool_credittype
            and m._dbt_source_project = f._dbt_source_project
            and f.rn_year = 1
        left join
            {{ ref("int_people__staff_roster") }} as r
            on m.teachernumber = r.powerschool_teacher_number
        where
            m.rn_course_number_year = 1
            and m.cc_sectionid > 0
            and m.cc_course_number not in (
                'LOG100',  -- Lunch
                'LOG1010',  -- Lunch
                'LOG11',  -- Lunch
                'LOG12',  -- Lunch
                'LOG20',  -- Early Dismissal
                'LOG22999XL',  -- Lunch
                'LOG300',  -- Study Hall
                'LOG9',  -- Lunch
                'SEM22106G1',  -- Advisory
                'SEM22106S1'  -- Not in SY24-25 yet
            )
    ),

    y1_final_grades as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            studentid,
            yearid,
            course_number,
            storecode,

            cast(`percent` as float64) as y1_course_final_percent_grade_adjusted,

            grade as y1_course_final_letter_grade_adjusted,
            earnedcrhrs as y1_course_final_earned_credits,
            potentialcrhrs as y1_course_final_potential_credit_hours,
            gpa_points as y1_course_final_grade_points,

        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode = 'Y1' and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    backfill_quarter_running as (
        /* TODO(#4687): TEMPORARY. Delete this CTE, backfill_course_anchored,
           backfill_running_course, and their use in quarter_grades branch 3
           once the dashboard runs on current-year data. Tracked in Asana under
           GPA and Gradebook Dashboard v3, Phase 4.

           Reconstructs a running year-to-date course percent for the prior
           year, which PowerSchool never stored. Q1 is exact by definition;
           Q2 and Q3 are approximations; Q4 is replaced by the stored Y1 value
           below so it matches exactly. Simple rather than credit-weighted
           average because the two agree to within half a point on 97.0 percent
           of courses. */
        select
            _dbt_source_relation,
            _dbt_source_project,
            studentid,
            yearid,
            course_number,
            storecode,
            gradescale_name_unweighted,

            avg(`percent`) over (
                partition by _dbt_source_project, studentid, yearid, course_number
                order by storecode
            ) as running_percent,
        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode in ('Q1', 'Q2', 'Q3', 'Q4')
            and academic_year = {{ var("current_academic_year") - 1 }}
    ),

    backfill_y1_stored_raw as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running. */
        select
            _dbt_source_project,
            studentid,
            yearid,
            course_number,
            gradescale_name_unweighted,
            dcid,

            `percent` as y1_stored_percent,
        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode = 'Y1' and academic_year = {{ var("current_academic_year") - 1 }}
    ),

    backfill_y1_stored as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running.

           dbt_utils.deduplicate guards the pre-existing #3915 storedgrades
           double-write, confirmed present on academic_year 2025 Y1 rows with
           genuinely conflicting percents rather than harmless repeats. Left
           un-deduplicated, this CTE's grain becomes a join key in
           backfill_course_anchored below, so one duplicate would multiply
           every quarter row for the course, not just the Y1 row it
           originated on. Highest dcid wins: sampled duplicate pairs cluster
           in two distinct dcid ranges, consistent with a later corrective
           re-import superseding an earlier one. */
        {{
            dbt_utils.deduplicate(
                relation="backfill_y1_stored_raw",
                partition_by="_dbt_source_project, studentid, yearid, course_number",
                order_by="dcid desc",
            )
        }}
    ),

    backfill_course_anchored as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running.

           Q4 takes the stored Y1 percent verbatim so the reconstruction lands
           exactly on the year grade. The Y1 storecode row is unioned in
           carrying the same value, so the Y1 marking period and Q4 agree. */
        select
            r._dbt_source_project,
            r.studentid,
            r.yearid,
            r.course_number,
            r.storecode,
            r.gradescale_name_unweighted,

            if(
                r.storecode = 'Q4', y1.y1_stored_percent, r.running_percent
            ) as anchored_percent,
        from backfill_quarter_running as r
        left join
            backfill_y1_stored as y1
            on r._dbt_source_project = y1._dbt_source_project
            and r.studentid = y1.studentid
            and r.yearid = y1.yearid
            and r.course_number = y1.course_number

        union all

        select
            _dbt_source_project,
            studentid,
            yearid,
            course_number,

            'Y1' as storecode,

            gradescale_name_unweighted,
            y1_stored_percent as anchored_percent,
        from backfill_y1_stored
    ),

    backfill_running_course as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running.

           Bands the reconstructed percent back to a letter on the course's own
           scale. Joins on gradescale_name rather than gradescaleid, the pattern
           int_powerschool__gpa_term and rpt_deanslist__transcript_gpas already
           use for storedgrades, plus _dbt_source_project because scale
           identifiers collide across districts. */
        select
            a._dbt_source_project,
            a.studentid,
            a.yearid,
            a.course_number,
            a.storecode,
            a.anchored_percent,

            gsi.letter_grade as anchored_letter_grade,
        from backfill_course_anchored as a
        left join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as gsi
            on a._dbt_source_project = gsi._dbt_source_project
            and a.gradescale_name_unweighted = gsi.gradescale_name
            and a.anchored_percent
            between gsi.min_cutoffpercentage and gsi.max_cutoffpercentage
    ),

    quarter_grades as (
        /* current year: live gradebook */
        select
            _dbt_source_relation,
            _dbt_source_project,
            studentid,
            yearid,
            course_number,

            storecode as `quarter`,

            term_percent_grade_adjusted as quarter_course_percent_grade,
            term_letter_grade_adjusted as quarter_course_letter_grade,
            term_grade_points as quarter_course_grade_points,
            y1_percent_grade_adjusted as y1_course_in_progress_percent_grade_adjusted,
            y1_letter_grade_adjusted as y1_course_in_progress_letter_grade_adjusted,
            y1_grade_points as y1_course_in_progress_grade_points,
            y1_grade_points_unweighted as y1_course_in_progress_grade_points_unweighted,

            need_60,
            need_70,
            need_80,
            need_90,

            courses_gradescaleid,

        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and not is_dropped_section
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')

        union all

        /* current year: in-progress Y1 row */
        select
            _dbt_source_relation,
            _dbt_source_project,
            studentid,
            yearid,
            course_number,

            'Y1' as `quarter`,

            y1_percent_grade_adjusted as quarter_course_percent_grade,
            y1_letter_grade_adjusted as quarter_course_letter_grade,
            y1_grade_points as quarter_course_grade_points,
            y1_percent_grade_adjusted as y1_course_in_progress_percent_grade_adjusted,
            y1_letter_grade_adjusted as y1_course_in_progress_letter_grade_adjusted,
            y1_grade_points as y1_course_in_progress_grade_points,
            y1_grade_points_unweighted as y1_course_in_progress_grade_points_unweighted,

            need_60,
            need_70,
            need_80,
            need_90,

            courses_gradescaleid,

        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and termbin_is_current
            and not is_dropped_section

        union all

        /* prior year: stored grades (Q1-Q4 term rows plus the stored Y1 row,
           which fills the quarter columns on Y1 rows like the in-progress
           branch does for the current year) */
        select
            sg._dbt_source_relation,
            sg._dbt_source_project,
            sg.studentid,
            sg.yearid,
            sg.course_number,

            sg.storecode as `quarter`,

            cast(sg.`percent` as float64) as quarter_course_percent_grade,
            sg.grade as quarter_course_letter_grade,
            sg.gpa_points as quarter_course_grade_points,

            bfc.anchored_percent as y1_course_in_progress_percent_grade_adjusted,
            bfc.anchored_letter_grade as y1_course_in_progress_letter_grade_adjusted,
            cast(null as float64) as y1_course_in_progress_grade_points,
            cast(null as float64) as y1_course_in_progress_grade_points_unweighted,

            cast(null as float64) as need_60,
            cast(null as float64) as need_70,
            cast(null as float64) as need_80,
            cast(null as float64) as need_90,

            cast(null as int64) as courses_gradescaleid,

        from {{ ref("stg_powerschool__storedgrades") }} as sg
        left join
            backfill_running_course as bfc
            on sg._dbt_source_project = bfc._dbt_source_project
            and sg.studentid = bfc.studentid
            and sg.yearid = bfc.yearid
            and sg.course_number = bfc.course_number
            and sg.storecode = bfc.storecode
        where
            sg.storecode in ('Q1', 'Q2', 'Q3', 'Q4', 'Y1')
            and sg.academic_year = {{ var("current_academic_year") - 1 }}
    ),

    grade_scale_rungs as (
        /* Whole-letter rungs only, no plus-minus, taken from each course's OWN
           scale — so the cutoffs genuinely differ. A D is 63 on KIPP NJ 2019
           but 60 on KIPP NJ 2016, which carries no D+/D-, and NCA 2011 has no
           A-. A hardcoded 60/70/80/90 ladder is wrong for roughly one Newark
           row in seven.

           Bands are recomputed here rather than reusing the lookup's own
           max_cutoffpercentage, which is unusable for this: that window
           partitions by scale id alone, so a scale carrying two items at one
           cutoff makes lead() repeat the value and collapses the band to
           max = min - 0.1 (119 of 976 rows). Restricting to whole letters
           leaves no duplicate cutoffs at all. _dbt_source_project is in the
           partition and the join because scale ids collide across districts —
           a bare gradescaleid join fans out about 1.8x. */
        select
            _dbt_source_project,
            gradescaleid,
            min_cutoffpercentage,

            row_number() over (
                partition by _dbt_source_project, gradescaleid
                order by min_cutoffpercentage
            ) as rung_number,

            lead(letter_grade) over (
                partition by _dbt_source_project, gradescaleid
                order by min_cutoffpercentage
            ) as need_next_letter_grade,

            lead(min_cutoffpercentage) over (
                partition by _dbt_source_project, gradescaleid
                order by min_cutoffpercentage
            ) as need_next_cutoff_percent,

            lead(min_cutoffpercentage, 1, 1000) over (
                partition by _dbt_source_project, gradescaleid
                order by min_cutoffpercentage
            )
            - 0.1 as rung_ceiling,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        where letter_grade in ('A', 'B', 'C', 'D', 'F')
    ),

    grade_scale_ladder as (
        /* the bottom rung floors at 0 so a percent below the F cutoff — the F*
           range on scales that split the two — still lands on a rung */
        select
            _dbt_source_project,
            gradescaleid,
            need_next_letter_grade,
            need_next_cutoff_percent,
            rung_ceiling,

            if(rung_number = 1, 0, min_cutoffpercentage) as rung_floor,
        from grade_scale_rungs
    ),

    category_grades as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            yearid,
            schoolid,
            studentid,
            course_number,
            sectionid,
            storecode_type as category_name_code,
            storecode as category_quarter_code,
            percent_grade as category_quarter_percent_grade,
            percent_grade_y1_running as category_y1_percent_grade_running,

            concat('Q', storecode_order) as term,

            avg(if(is_current, percent_grade_y1_running, null)) over (
                partition by
                    _dbt_source_relation,
                    studentid,
                    yearid,
                    course_number,
                    storecode_type
            ) as category_y1_percent_grade_current,

            round(
                avg(percent_grade) over (
                    partition by _dbt_source_relation, yearid, studentid, storecode
                ),
                2
            ) as category_quarter_average_all_courses,

        from {{ ref("int_powerschool__category_grades") }}
        where
            yearid >= {{ var("current_academic_year") - 1991 }}
            and not is_dropped_section
            and storecode_type not in ('Q')
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')
    ),

    category_ranked as (
        /* Ranking input for the lowest-category drivers. Rows where BOTH
           percents are null are excluded so a term that exists but carries no
           usable value cannot win rn_latest_term and blank out both drivers.

           (percent is null) asc leads each order by because BigQuery sorts
           NULLS FIRST ascending, which would otherwise hand "lowest" to a null.
           category_name_code is the final tiebreaker so the pick is
           reproducible across rebuilds. */
        select
            _dbt_source_project,
            studentid,
            yearid,
            sectionid,
            category_name_code,
            category_quarter_percent_grade,
            category_y1_percent_grade_running,

            dense_rank() over (
                partition by _dbt_source_project, studentid, yearid, sectionid
                order by term desc
            ) as rn_latest_term,

            row_number() over (
                partition by _dbt_source_project, studentid, yearid, sectionid, term
                order by
                    (category_y1_percent_grade_running is null) asc,
                    category_y1_percent_grade_running asc,
                    category_name_code asc
            ) as rn_lowest_y1,

            row_number() over (
                partition by _dbt_source_project, studentid, yearid, sectionid, term
                order by
                    (category_quarter_percent_grade is null) asc,
                    category_quarter_percent_grade asc,
                    category_name_code asc
            ) as rn_lowest_quarter,
        from category_grades
        where
            category_quarter_percent_grade is not null
            or category_y1_percent_grade_running is not null
    ),

    category_drivers as (
        /* One row per student-section-year, so the join below cannot fan out.
           Both drivers are read from the SAME latest term, so they describe one
           moment rather than two. */
        select
            _dbt_source_project,
            studentid,
            yearid,
            sectionid,

            max(
                if(
                    rn_lowest_y1 = 1 and category_y1_percent_grade_running is not null,
                    category_name_code,
                    null
                )
            ) as lowest_category_y1_name,

            max(
                if(rn_lowest_y1 = 1, category_y1_percent_grade_running, null)
            ) as lowest_category_y1_percent,

            max(
                if(
                    rn_lowest_quarter = 1
                    and category_quarter_percent_grade is not null,
                    category_name_code,
                    null
                )
            ) as lowest_category_recent_term_name,

            max(
                if(rn_lowest_quarter = 1, category_quarter_percent_grade, null)
            ) as lowest_category_recent_term_percent,
        from category_ranked
        where rn_latest_term = 1
        group by _dbt_source_project, studentid, yearid, sectionid
    )

select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.salesforce_id,
    s.ktc_cohort,
    s.enroll_status,
    s.cohort,
    s.graduation_year,
    s.gender,
    s.ethnicity,
    s.advisory,
    s.hos,
    s.school_leader,
    s.school_leader_tableau_username,
    s.year_in_school,
    s.year_in_network,
    s.rn_undergrad,
    s.is_out_of_district,
    s.is_pathways,
    s.is_retained_year,
    s.is_retained_ever,
    s.student_slideback,
    s.lunch_status,
    s.gifted_and_talented,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,
    s.ada,
    s.unweighted_ada,
    s.weighted_ada,
    s.ada_above_or_at_80,

    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,
    s.is_current_academic_year,

    s.gpa_for_quarter,
    s.gpa_semester,
    s.gpa_y1,
    s.gpa_y1_unweighted,
    s.gpa_total_credit_hours,
    s.gpa_n_failing_y1,

    s.gpa_y1_1_week_prior,
    s.gpa_y1_2_week_prior,
    s.gpa_y1_4_week_prior,
    s.gpa_y1_unweighted_1_week_prior,
    s.gpa_y1_unweighted_2_week_prior,
    s.gpa_y1_unweighted_4_week_prior,
    s.n_failing_y1_1_week_prior,
    s.n_failing_y1_2_week_prior,
    s.n_failing_y1_4_week_prior,

    s.gpa_y1_prior_quarter,
    s.n_failing_y1_prior_quarter,
    s.gpa_y1_prior_year,

    s.cumulative_y1_gpa,
    s.cumulative_y1_gpa_unweighted,
    s.cumulative_y1_gpa_projected,
    s.cumulative_y1_gpa_projected_unweighted,
    s.cumulative_y1_gpa_projected_s1,
    s.cumulative_y1_gpa_projected_s1_unweighted,
    s.core_cumulative_y1_gpa,
    s.potential_gpa_credits_cum_projected,
    s.potential_gpa_credits_current_year,
    s.gpa_needed_for_cumulative_3_0,
    s.is_cumulative_3_0_attainable,
    s.cumulative_y1_gpa_unweighted_prior_year,
    s.gpa_band_projected_unweighted,
    s.gpa_band_unweighted_prior_year,

    ce.sectionid,
    ce.sections_dcid,
    ce.section_number,
    ce.external_expression,
    ce.date_enrolled,
    ce.credit_type,
    ce.course_number,
    ce.course_name,
    ce.exclude_from_gpa,
    ce.teacher_number,
    ce.teacher_name,
    ce.teacher_tableau_username,
    ce.manager,
    ce.report_to_sam_account_name,
    ce.tutoring_nj,
    ce.nj_student_tier,

    y1f.y1_course_final_percent_grade_adjusted,
    y1f.y1_course_final_letter_grade_adjusted,
    y1f.y1_course_final_earned_credits,
    y1f.y1_course_final_potential_credit_hours,
    y1f.y1_course_final_grade_points,

    qg.quarter_course_percent_grade,
    qg.quarter_course_letter_grade,
    qg.quarter_course_grade_points,
    qg.y1_course_in_progress_percent_grade_adjusted,
    qg.y1_course_in_progress_letter_grade_adjusted,
    qg.y1_course_in_progress_grade_points,
    qg.y1_course_in_progress_grade_points_unweighted,
    qg.need_60,
    qg.need_70,
    qg.need_80,
    qg.need_90,

    c.category_name_code,
    c.category_quarter_code,
    c.category_quarter_percent_grade,
    c.category_y1_percent_grade_running,
    c.category_y1_percent_grade_current,
    c.category_quarter_average_all_courses,

    cd.lowest_category_y1_name,
    cd.lowest_category_y1_percent,
    cd.lowest_category_recent_term_name,
    cd.lowest_category_recent_term_percent,

    gsl.need_next_letter_grade,
    gsl.need_next_cutoff_percent,

    /* signed, so negative means the projection sits below last year's actual.
       Both inputs are student-grain, so these repeat across every quarter row
       and the Y1 row for a student, which is what makes them filterable at any
       marking period. */
    s.cumulative_y1_gpa_projected_unweighted
    - s.cumulative_y1_gpa_unweighted_prior_year
    as cumulative_y1_gpa_unweighted_change_from_prior_year,

    s.gpa_band_projected_unweighted
    - s.gpa_band_unweighted_prior_year as gpa_band_change_from_prior_year,

    /* need_* is affine in the target percent — it is
       (points_still_needed * target - points_banked) / (term_points / 100), and
       the three non-target terms are row constants — so the need for ANY target
       is exactly recoverable from two of the four existing columns, and the
       CTE-internal point columns never have to cross the package boundary.
       Reduces to need_60 + (target - 60) / 10 * (need_70 - need_60); at target
       70 it returns need_70 identically, by construction.

       Like the four it is derived from, this is the percent required IN THE
       CURRENT TERM to land the YEAR-TO-DATE grade on the next rung — not what
       is needed for that letter this quarter. */
    qg.need_60
    + (gsl.need_next_cutoff_percent - 60) / 10 * (qg.need_70 - qg.need_60) as need_next,

    coalesce(
        y1f.y1_course_final_letter_grade_adjusted,
        qg.y1_course_in_progress_letter_grade_adjusted
    ) as y1_course_letter_grade_adjusted,

    if(
        s.grade_level < 9, ce.section_number, ce.external_expression
    ) as section_or_period,

    /* NULL rather than false when either side is missing — an unbanded student
       is unknown, not known-to-be-holding-steady */
    s.gpa_band_projected_unweighted
    <= s.gpa_band_unweighted_prior_year - 1 as is_gpa_band_slide,

    /* prefix match, not = 'F', because the failing domain is F and F*. F* is
       not a PowerSchool grade — stg_powerschool__pgfinalgrades manufactures it
       alongside the 50% floor (if percent < 0.5 then 'F*'), so an exact-equality
       test silently drops every floored failure, roughly a third of them. This
       matches the canonical rule the warehouse already uses for n_failing_y1.

       NULL, not false, on an ungraded enrolment — no grade posted is unknown,
       not known-to-be-passing. Consumers computing a failure rate should divide
       by the count of non-null quarter_course_letter_grade, not by all rows.

       The Y1 row carries the Y1 letter grade in this same column, so one flag
       covers Q1-Q4 and Y1 with no marking-period branching. */
    qg.quarter_course_letter_grade like 'F%' as is_quarter_course_failing,

from student_roster as s
left join
    course_enrollments as ce
    on s.studentid = ce.studentid
    and s.yearid = ce.yearid
    and s._dbt_source_project = ce._dbt_source_project
left join
    y1_final_grades as y1f
    on s.studentid = y1f.studentid
    and s.yearid = y1f.yearid
    and s.`quarter` = y1f.storecode
    and s._dbt_source_project = y1f._dbt_source_project
    and ce.course_number = y1f.course_number
    and ce._dbt_source_project = y1f._dbt_source_project
left join
    quarter_grades as qg
    on s.studentid = qg.studentid
    and s.yearid = qg.yearid
    and s.`quarter` = qg.`quarter`
    and s._dbt_source_project = qg._dbt_source_project
    and ce.course_number = qg.course_number
    and ce._dbt_source_project = qg._dbt_source_project
left join
    category_grades as c
    on s.studentid = c.studentid
    and s.yearid = c.yearid
    and s.`quarter` = c.term
    and s._dbt_source_project = c._dbt_source_project
    and ce.sectionid = c.sectionid
    and ce._dbt_source_project = c._dbt_source_project
left join
    grade_scale_ladder as gsl
    on qg._dbt_source_project = gsl._dbt_source_project
    and qg.courses_gradescaleid = gsl.gradescaleid
    and qg.y1_course_in_progress_percent_grade_adjusted
    between gsl.rung_floor and gsl.rung_ceiling
left join
    category_drivers as cd
    on s.studentid = cd.studentid
    and s.yearid = cd.yearid
    and s._dbt_source_project = cd._dbt_source_project
    and ce.sectionid = cd.sectionid
    and ce._dbt_source_project = cd._dbt_source_project
where s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
