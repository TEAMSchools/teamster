with
    course_enrollments as (
        select
            cc_studentid as studentid,
            cc_yearid as yearid,
            cc_academic_year as academic_year,
            cc_schoolid as schoolid,
            cc_course_number as course_number,
            cc_sectionid as sectionid,
            cc_dateenrolled as date_enrolled,
            sections_dcid,
            sections_section_number as section_number,
            sections_external_expression as external_expression,
            courses_credittype as credit_type,
            courses_course_name as course_name,
            courses_excludefromgpa as exclude_from_gpa,
            teachernumber as teacher_number,
            teacher_lastfirst as teacher_name,
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            cc_academic_year >= {{ var("current_academic_year") - 1 }}
            and cc_academic_year <= {{ var("current_academic_year") }}
            and rn_course_number_year = 1
            and cc_sectionid > 0
            and cc_course_number not in (
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

    term_spine as (
        /* grain projection, not dup-masking: (schoolid, yearid, term) */
        select distinct schoolid, yearid, term as `quarter`,
        from {{ ref("int_powerschool__terms") }}
        where term like 'Q%'

        union all

        /* grain projection, not dup-masking: (schoolid, yearid) */
        select distinct schoolid, yearid, 'Y1' as `quarter`,
        from {{ ref("int_powerschool__terms") }}
    ),

    y1_final_grades as (
        select
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
            studentid,
            yearid,
            course_number,
            storecode,
            gradescale_name_unweighted,

            avg(`percent`) over (
                partition by studentid, yearid, course_number order by storecode
            ) as running_percent,
        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode in ('Q1', 'Q2', 'Q3', 'Q4')
            and academic_year = {{ var("current_academic_year") - 1 }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    backfill_y1_stored_raw as (
        /* TODO(#4687): TEMPORARY, see backfill_quarter_running. */
        select
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
                partition_by="studentid, yearid, course_number",
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
            on r.studentid = y1.studentid
            and r.yearid = y1.yearid
            and r.course_number = y1.course_number

        union all

        select
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
           use for storedgrades. */
        select
            a.studentid,
            a.yearid,
            a.course_number,
            a.storecode,
            a.anchored_percent,

            gsi.letter_grade as anchored_letter_grade,
        from backfill_course_anchored as a
        left join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as gsi
            on a.gradescale_name_unweighted = gsi.gradescale_name
            and a.anchored_percent
            between gsi.min_cutoffpercentage and gsi.max_cutoffpercentage
    ),

    quarter_grades as (
        /* current year: live gradebook */
        select
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
            on sg.studentid = bfc.studentid
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
           leaves no duplicate cutoffs at all. */
        select
            gradescaleid,
            min_cutoffpercentage,

            row_number() over (
                partition by gradescaleid order by min_cutoffpercentage
            ) as rung_number,

            lead(letter_grade) over (
                partition by gradescaleid order by min_cutoffpercentage
            ) as need_next_letter_grade,

            lead(min_cutoffpercentage) over (
                partition by gradescaleid order by min_cutoffpercentage
            ) as need_next_cutoff_percent,

            lead(min_cutoffpercentage, 1, 1000) over (
                partition by gradescaleid order by min_cutoffpercentage
            )
            - 0.1 as rung_ceiling,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        where letter_grade in ('A', 'B', 'C', 'D', 'F')
    ),

    grade_scale_ladder as (
        /* the bottom rung floors at 0 so a percent below the F cutoff — the F*
           range on scales that split the two — still lands on a rung */
        select
            gradescaleid,
            need_next_letter_grade,
            need_next_cutoff_percent,
            rung_ceiling,

            if(rung_number = 1, 0, min_cutoffpercentage) as rung_floor,
        from grade_scale_rungs
    ),

    category_grades as (
        select
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
                partition by studentid, yearid, course_number, storecode_type
            ) as category_y1_percent_grade_current,

            round(
                avg(percent_grade) over (partition by yearid, studentid, storecode), 2
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
            studentid,
            yearid,
            sectionid,
            category_name_code,
            category_quarter_percent_grade,
            category_y1_percent_grade_running,

            dense_rank() over (
                partition by studentid, yearid, sectionid order by term desc
            ) as rn_latest_term,

            row_number() over (
                partition by studentid, yearid, sectionid, term
                order by
                    (category_y1_percent_grade_running is null) asc,
                    category_y1_percent_grade_running asc,
                    category_name_code asc
            ) as rn_lowest_y1,

            row_number() over (
                partition by studentid, yearid, sectionid, term
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
        group by studentid, yearid, sectionid
    ),

    course_priority as (
        /* No (x is null) asc guard, unlike category_ranked above — the
           filter removes nulls before the window runs, so an ungraded course
           takes no rank and the left join at the foot of the model is what
           nulls the column. */
        select
            studentid,
            yearid,
            `quarter`,
            course_number,

            row_number() over (
                partition by studentid, yearid, `quarter`
                order by quarter_course_percent_grade asc, course_number asc
            ) as office_hours_priority_rank,
        from quarter_grades
        where quarter_course_percent_grade is not null
    )

select
    ce.studentid,
    ce.yearid,
    ce.academic_year,
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

    ts.`quarter`,

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
    qg.courses_gradescaleid,

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

    cp.office_hours_priority_rank,

    /* need_* is affine in the target percent — it is
       (points_still_needed * target - points_banked) / (term_points / 100), and
       the three non-target terms are row constants — so the need for ANY target
       is exactly recoverable from two of the four existing columns.
       Reduces to need_60 + (target - 60) / 10 * (need_70 - need_60); at target
       70 it returns need_70 identically, by construction.

       Like the four it is derived from, this is the percent required IN THE
       CURRENT TERM to land the YEAR-TO-DATE grade on the next rung — not what
       is needed for that letter this quarter. */
    qg.need_60
    + (gsl.need_next_cutoff_percent - 60) / 10 * (qg.need_70 - qg.need_60) as need_next,
from course_enrollments as ce
inner join term_spine as ts on ce.schoolid = ts.schoolid and ce.yearid = ts.yearid
left join
    y1_final_grades as y1f
    on ce.studentid = y1f.studentid
    and ce.yearid = y1f.yearid
    and ce.course_number = y1f.course_number
    and ts.`quarter` = y1f.storecode
left join
    quarter_grades as qg
    on ce.studentid = qg.studentid
    and ce.yearid = qg.yearid
    and ce.course_number = qg.course_number
    and ts.`quarter` = qg.`quarter`
left join
    category_grades as c
    on ce.studentid = c.studentid
    and ce.yearid = c.yearid
    and ce.sectionid = c.sectionid
    and ts.`quarter` = c.term
left join
    grade_scale_ladder as gsl
    on qg.courses_gradescaleid = gsl.gradescaleid
    and qg.y1_course_in_progress_percent_grade_adjusted
    between gsl.rung_floor and gsl.rung_ceiling
left join
    category_drivers as cd
    on ce.studentid = cd.studentid
    and ce.yearid = cd.yearid
    and ce.sectionid = cd.sectionid
left join
    course_priority as cp
    on ce.studentid = cp.studentid
    and ce.yearid = cp.yearid
    and ce.course_number = cp.course_number
    and ts.`quarter` = cp.`quarter`
