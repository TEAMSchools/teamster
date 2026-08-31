with
    goals as (
        select
            test_type as expected_test_type,
            score_type as expected_score_type,
            expected_metric_name,
            expected_min_score as min_score,

        from {{ ref("int_google_sheets__kippfwd__goals_unpivot") }}
        where expected_goal_type = 'Benchmark' and goal_branch = 'All Grades'
    ),

    /* One row per student holding all three SAT highlights, replacing three
       separate left joins to the same model that differed only by subject area.
       Official only: superscore is not computed for practice. */
    sat_highlights as (
        select
            student_number,

            max(
                if(aligned_subject_area = 'Total', superscore, null)
            ) as sat_total_superscore,
            max(
                if(aligned_subject_area = 'EBRW', max_scale_score, null)
            ) as sat_ebrw_highest,
            max(
                if(aligned_subject_area = 'Math', max_scale_score, null)
            ) as sat_math_highest,

        from {{ ref("int_assessments__college_assessment") }}
        where
            scope = 'SAT'
            and rn_highest = 1
            and aligned_subject_area in ('Total', 'EBRW', 'Math')
        group by student_number
    ),

    final as (
        select
            e.region,
            e.schoolid,
            e.school,
            e.student_number,
            e.salesforce_id,
            e.student_name,
            e.student_first_name,
            e.student_last_name,
            e.grade_level,
            e.student_email,
            e.enroll_status_string as enroll_status,
            e.ktc_cohort,
            e.graduation_year,
            e.year_in_network,
            e.iep_status,
            e.grad_iep_exempt_status_overall,
            e.cumulative_y1_gpa,
            e.cumulative_y1_gpa_projected,
            e.college_match_gpa,
            e.college_match_gpa_bands,

            sc.scope,
            sc.test_date,
            sc.scale_score,

            /* Official or Practice. The test_type column below already carries the
               scope, so this cannot reuse that name. */
            sc.test_type as administration_type,

            g.expected_metric_name,

            sh.sat_total_superscore,
            sh.sat_ebrw_highest,
            sh.sat_math_highest,

            /* The bucket the three subject blocks below pivot on. Official rows
               carry it in aligned_subject, which folds SAT EBRW and ACT Reading
               into one EBRW/Reading value; practice rows leave that column null
               and carry the same vocabulary in aligned_subject_area. Reading
               only the latter would split official EBRW from official Reading,
               and reading only the former would drop every practice row. */
            coalesce(sc.aligned_subject, sc.aligned_subject_area) as pivot_subject,

            coalesce(c.courses_course_name, 'No Data') as ccr_course,
            coalesce(c.teacher_lastfirst, 'No Data') as ccr_teacher_name,
            coalesce(c.sections_external_expression, 'No Data') as ccr_section,

            if(sc.scale_score >= g.min_score, 'Yes', 'No') as met_minimum,
            if(sc.rn_highest = 1, 'Yes', 'No') as highest_score_by_test,

        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            {{ ref("int_assessments__all_college_assessments") }} as sc
            on e.student_number = sc.student_number
        left join
            goals as g
            on sc.test_type = g.expected_test_type
            and sc.score_type = g.expected_score_type
        left join sat_highlights as sh on e.student_number = sh.student_number
        left join
            {{ ref("base_powerschool__course_enrollments") }} as c
            on e.student_number = c.students_student_number
            and e.academic_year = c.cc_academic_year
            and c.rn_course_number_year = 1
            and not c.is_dropped_section
            and c.courses_course_name in (
                'College and Career IV',
                'College and Career I',
                'College and Career III',
                'College and Career II'
            )
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.graduation_year >= {{ var("current_academic_year") + 1 }}
            and e.school_level = 'HS'
            and e.rn_year = 1
            and e.enroll_status = 0
    ),

    pivoted as (
        select
            region,
            schoolid,
            school,
            student_number,
            salesforce_id,
            student_name,
            student_first_name,
            student_last_name,
            grade_level,
            student_email,
            enroll_status,
            ktc_cohort,
            graduation_year,
            year_in_network,
            iep_status,
            grad_iep_exempt_status_overall,
            cumulative_y1_gpa,
            cumulative_y1_gpa_projected,
            college_match_gpa,
            college_match_gpa_bands,

            /* Grouped, not aggregated. The CCR course/teacher/section triple
               comes from one joined row, so independent max() calls could pair a
               course with another row's teacher if a student ever held two
               College and Career sections in a year. Grouping keeps the triple
               intact and surfaces such a student as a duplicate row for the
               uniqueness test to flag, rather than silently blending two rows.
               Same reasoning for the three lifetime SAT highs, which tie-break
               independently on rn_highest. */
            ccr_course,
            ccr_teacher_name,
            ccr_section,
            sat_total_superscore,
            sat_ebrw_highest,
            sat_math_highest,
            scope as test_type,
            administration_type,
            test_date,

            /* max() over 'Yes'/'No' resolves to 'Yes', which is correct for both
               flags: the sitting is the student's highest, or meets the
               benchmark, if any duplicate upstream row says so. Duplicate
               kippadb records are tracked in #4871. 'NA' means no benchmark
               exists for that score type, distinct from a 'No' that missed one. */
            max(if(pivot_subject = 'Total', scale_score, null)) as total_scale_score,
            max(
                if(pivot_subject = 'Total', highest_score_by_test, null)
            ) as total_highest_score_by_test,
            coalesce(
                max(
                    if(
                        pivot_subject = 'Total'
                        and expected_metric_name = 'HS Grad-Ready',
                        met_minimum,
                        null
                    )
                ),
                'NA'
            ) as total_hs_grad_ready,
            coalesce(
                max(
                    if(
                        pivot_subject = 'Total'
                        and expected_metric_name = 'College-Ready',
                        met_minimum,
                        null
                    )
                ),
                'NA'
            ) as total_college_ready,

            max(
                if(pivot_subject = 'EBRW/Reading', scale_score, null)
            ) as ebrw_reading_scale_score,
            max(
                if(pivot_subject = 'EBRW/Reading', highest_score_by_test, null)
            ) as ebrw_reading_highest_score_by_test,
            coalesce(
                max(
                    if(
                        pivot_subject = 'EBRW/Reading'
                        and expected_metric_name = 'HS Grad-Ready',
                        met_minimum,
                        null
                    )
                ),
                'NA'
            ) as ebrw_reading_hs_grad_ready,
            coalesce(
                max(
                    if(
                        pivot_subject = 'EBRW/Reading'
                        and expected_metric_name = 'College-Ready',
                        met_minimum,
                        null
                    )
                ),
                'NA'
            ) as ebrw_reading_college_ready,

            max(if(pivot_subject = 'Math', scale_score, null)) as math_scale_score,
            max(
                if(pivot_subject = 'Math', highest_score_by_test, null)
            ) as math_highest_score_by_test,
            coalesce(
                max(
                    if(
                        pivot_subject = 'Math'
                        and expected_metric_name = 'HS Grad-Ready',
                        met_minimum,
                        null
                    )
                ),
                'NA'
            ) as math_hs_grad_ready,
            coalesce(
                max(
                    if(
                        pivot_subject = 'Math'
                        and expected_metric_name = 'College-Ready',
                        met_minimum,
                        null
                    )
                ),
                'NA'
            ) as math_college_ready,

        from final
        /* The three subjects pivoted above. Equivalent to the prior score_type
           exclusion list: every excluded score_type maps to Reading, Math Test,
           Reading Test, English or Science. Being a positive filter, it also
           excludes students with no qualifying score, which the prior list did
           implicitly -- a null score_type never satisfied `not in`. */
        where pivot_subject in ('Total', 'EBRW/Reading', 'Math')
        group by
            region,
            schoolid,
            school,
            student_number,
            salesforce_id,
            student_name,
            student_first_name,
            student_last_name,
            grade_level,
            student_email,
            enroll_status,
            ktc_cohort,
            graduation_year,
            year_in_network,
            iep_status,
            grad_iep_exempt_status_overall,
            cumulative_y1_gpa,
            cumulative_y1_gpa_projected,
            college_match_gpa,
            college_match_gpa_bands,
            ccr_course,
            ccr_teacher_name,
            ccr_section,
            sat_total_superscore,
            sat_ebrw_highest,
            sat_math_highest,
            scope,
            administration_type,
            test_date
    )

select
    region,
    schoolid,
    school,
    student_number,
    salesforce_id,
    student_name,
    student_first_name,
    student_last_name,
    grade_level,
    student_email,
    enroll_status,
    ktc_cohort,
    graduation_year,
    year_in_network,
    iep_status,
    grad_iep_exempt_status_overall,
    cumulative_y1_gpa,
    cumulative_y1_gpa_projected,
    college_match_gpa,
    college_match_gpa_bands,
    ccr_course,
    ccr_teacher_name,
    ccr_section,

    sat_total_superscore as `SAT Composite Superscore`,
    sat_ebrw_highest as `SAT Highest EBRW Score`,
    sat_math_highest as `SAT Highest Math Score`,

    test_type,
    administration_type,
    test_date,

    total_scale_score as `Composite Score`,
    total_highest_score_by_test,
    total_hs_grad_ready as `Meeting High School Grad Benchmark - Composite`,
    total_college_ready as `Meeting College Ready Benchmark - Composite`,

    ebrw_reading_scale_score as `EBRW Score`,
    ebrw_reading_highest_score_by_test,
    ebrw_reading_hs_grad_ready as `Meeting HS Grad Benchmark - EBRW`,
    ebrw_reading_college_ready as `Meeting College Ready Benchmark - EBRW`,

    math_scale_score as `Math Score`,
    math_highest_score_by_test,
    math_hs_grad_ready as `Meeting High School Grad Benchmark - Math`,
    math_college_ready as `Meeting College Ready Benchmark - Math`,

from pivoted
