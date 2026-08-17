with
    goals_distinct as (
        select
            expected_test_type,
            expected_score_type,
            expected_metric_name,

            avg(min_score) as min_score,

        from {{ ref("stg_google_sheets__kippfwd__goals") }}
        where expected_goal_type = 'Benchmark' and region is null and schoolid is null
        group by expected_test_type, expected_score_type, expected_metric_name
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
            sc.aligned_subject,
            sc.test_date,
            sc.scale_score,

            g.expected_metric_name,

            ss.superscore as sat_total_superscore,

            he.max_scale_score as sat_ebrw_highest,

            hm.max_scale_score as sat_math_highest,

            coalesce(c.courses_course_name, 'No Data') as ccr_course,
            coalesce(c.teacher_lastfirst, 'No Data') as ccr_teacher_name,
            coalesce(c.sections_external_expression, 'No Data') as ccr_section,

            if(sc.scale_score >= g.min_score, 'Yes', 'No') as met_minimum,
            if(sc.rn_highest = 1, 'Yes', 'No') as highest_score_by_test,

        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            {{ ref("int_assessments__college_assessment") }} as sc
            on e.student_number = sc.student_number
        left join
            goals_distinct as g
            on sc.test_type = g.expected_test_type
            and sc.score_type = g.expected_score_type
        left join
            {{ ref("int_assessments__college_assessment") }} as ss
            on e.student_number = ss.student_number
            and ss.scope = 'SAT'
            and ss.aligned_subject_area = 'Total'
            and ss.rn_highest = 1
        left join
            {{ ref("int_assessments__college_assessment") }} as he
            on e.student_number = he.student_number
            and he.scope = 'SAT'
            and he.aligned_subject_area = 'EBRW'
            and he.rn_highest = 1
        left join
            {{ ref("int_assessments__college_assessment") }} as hm
            on e.student_number = hm.student_number
            and hm.scope = 'SAT'
            and hm.aligned_subject_area = 'Math'
            and hm.rn_highest = 1
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
            /*
            The three subjects pivoted below. Equivalent to the prior
            score_type exclusion list: every excluded score_type maps to
            Reading, Math Test, Reading Test, English or Science. Being a
            positive filter, it also excludes students with no qualifying
            score, which the prior list did implicitly -- a null score_type
            never satisfied `not in`.
            */
            and sc.aligned_subject in ('Total', 'EBRW/Reading', 'Math')
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
            scope as test_type,
            test_date,

            /*
            Aggregated rather than grouped: a student enrolled in two College
            and Career sections, or a tie on the rn_highest superscore joins,
            would otherwise split the row and break the grain.
            */
            max(ccr_course) as ccr_course,
            max(ccr_teacher_name) as ccr_teacher_name,
            max(ccr_section) as ccr_section,
            max(sat_total_superscore) as sat_total_superscore,
            max(sat_ebrw_highest) as sat_ebrw_highest,
            max(sat_math_highest) as sat_math_highest,

            /*
            max() over 'Yes'/'No' resolves to 'Yes', which is correct for both
            flags: the sitting is the student's highest, or meets the
            benchmark, if any duplicate upstream row says so. Duplicate
            kippadb records are tracked in #4871.
            */
            max(if(aligned_subject = 'Total', scale_score, null)) as total_scale_score,
            max(
                if(aligned_subject = 'Total', highest_score_by_test, null)
            ) as total_highest_score_by_test,
            max(
                if(
                    aligned_subject = 'Total' and expected_metric_name = 'HS-Ready',
                    met_minimum,
                    null
                )
            ) as total_hs_grad_ready,
            max(
                if(
                    aligned_subject = 'Total'
                    and expected_metric_name = 'College-Ready',
                    met_minimum,
                    null
                )
            ) as total_college_ready,

            max(
                if(aligned_subject = 'EBRW/Reading', scale_score, null)
            ) as ebrw_reading_scale_score,
            max(
                if(aligned_subject = 'EBRW/Reading', highest_score_by_test, null)
            ) as ebrw_reading_highest_score_by_test,
            max(
                if(
                    aligned_subject = 'EBRW/Reading'
                    and expected_metric_name = 'HS-Ready',
                    met_minimum,
                    null
                )
            ) as ebrw_reading_hs_grad_ready,
            max(
                if(
                    aligned_subject = 'EBRW/Reading'
                    and expected_metric_name = 'College-Ready',
                    met_minimum,
                    null
                )
            ) as ebrw_reading_college_ready,

            max(if(aligned_subject = 'Math', scale_score, null)) as math_scale_score,
            max(
                if(aligned_subject = 'Math', highest_score_by_test, null)
            ) as math_highest_score_by_test,
            max(
                if(
                    aligned_subject = 'Math' and expected_metric_name = 'HS-Ready',
                    met_minimum,
                    null
                )
            ) as math_hs_grad_ready,
            max(
                if(
                    aligned_subject = 'Math' and expected_metric_name = 'College-Ready',
                    met_minimum,
                    null
                )
            ) as math_college_ready,

        from final
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
            scope,
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

    sat_total_superscore,
    sat_ebrw_highest,
    sat_math_highest,

    test_type,
    test_date,

    total_scale_score,
    total_highest_score_by_test,
    coalesce(total_hs_grad_ready, 'NA') as total_hs_grad_ready,
    coalesce(total_college_ready, 'NA') as total_college_ready,

    ebrw_reading_scale_score,
    ebrw_reading_highest_score_by_test,
    coalesce(ebrw_reading_hs_grad_ready, 'NA') as ebrw_reading_hs_grad_ready,
    coalesce(ebrw_reading_college_ready, 'NA') as ebrw_reading_college_ready,

    math_scale_score,
    math_highest_score_by_test,
    coalesce(math_hs_grad_ready, 'NA') as math_hs_grad_ready,
    coalesce(math_college_ready, 'NA') as math_college_ready,

from pivoted
