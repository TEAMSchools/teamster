with
    scores as (
        select
            student_number,
            unique_test_admin_id,
            scale_score as score,

            'Scale Score' as score_category,

        from {{ ref("int_tableau__college_assessment_roster_scores") }}

        union all

        select
            student_number,
            unique_test_admin_id,
            total_growth_score_change as score,

            'Score Change' as score_category,

        from {{ ref("int_tableau__college_assessment_roster_scores") }}
    ),
    roster as (
        select
            e.student_number,
            e.salesforce_id,
            e.student_name,
            e.student_first_name,
            e.student_last_name,
            e.student_email,
            e.region,
            e.school,
            e.grade_level,
            e.enroll_status,
            e.graduation_year,
            e.ktc_cohort,
            e.year_in_network,
            e.iep_status,
            e.grad_iep_exempt_status_overall,
            e.cumulative_y1_gpa,
            e.cumulative_y1_gpa_projected,
            e.college_match_gpa,
            e.college_match_gpa_bands,

            ea.expected_admin_season_order,
            ea.expected_score_type,
            ea.expected_admin_season,
            ea.expected_grade_level,

            a.score,

            ss.superscore as sat_total_superscore,

            he.max_scale_score as sat_ebrw_highest,

            hm.max_scale_score as sat_math_highest,

            coalesce(c.teacher_lastfirst, 'No Data') as ccr_teacher_name,
            coalesce(c.sections_external_expression, 'No Data') as ccr_section,

            coalesce(p.psat89_count_lifetime, 0) as psat89_count_lifetime,
            coalesce(p.psat10_count_lifetime, 0) as psat10_count_lifetime,
            coalesce(p.psatnmsqt_count_lifetime, 0) as psatnmsqt_count_lifetime,
            coalesce(p.sat_count_lifetime, 0) as sat_count_lifetime,
        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("stg_google_sheets__kippfwd__expected_assessments") }} as ea
            on e.region = ea.expected_region
            and ea.rn = 1
        left join
            scores as a
            on e.student_number = a.student_number
            and ea.expected_unique_test_admin_id = a.unique_test_admin_id
            and ea.expected_score_category = a.score_category
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
        left join
            {{ ref("int_students__college_assessment_participation_roster") }} as p
            on e.student_number = p.student_number
            and p.rn_lifetime = 1
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.graduation_year >= {{ var("current_academic_year") + 1 }}
            and e.school_level = 'HS'
            and e.rn_year = 1
            and not e.is_out_of_district
            and e.enroll_status = 0
            and ea.expected_admin_season_order is not null
    ),
    first_sat as (
        select school_specific_id as student_number, min(`date`) as first_sat_date,
        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where score_type = 'sat_total_score' and `date` is not null
        group by school_specific_id
    ),
    earliest_sat as (
        select s.school_specific_id as student_number, s.score as earliest_sat_total,
        from {{ ref("int_kippadb__standardized_test_unpivot") }} as s
        inner join
            first_sat as f
            on s.school_specific_id = f.student_number
            and s.`date` = f.first_sat_date
        where s.score_type = 'sat_total_score'
        qualify
            row_number() over (partition by s.school_specific_id order by s.score desc)
            = 1
    ),
    latest_psat_before_first_sat as (
        select
            p.powerschool_student_number as student_number,
            p.score as latest_psat_total,
            p.score_type as psat_score_type,
            p.latest_psat_date as psat_date,
        from {{ ref("int_collegeboard__psat_unpivot") }} as p
        inner join
            first_sat as f
            on p.powerschool_student_number = f.student_number
            and p.latest_psat_date < f.first_sat_date
        where p.score_type in ('psat89_total', 'psat10_total', 'psatnmsqt_total')
        qualify
            row_number() over (
                partition by p.powerschool_student_number
                order by p.latest_psat_date desc
            )
            = 1
    )
select
    r.student_number,
    r.salesforce_id,
    r.student_name,
    r.student_first_name,
    r.student_last_name,
    r.student_email,
    r.region,
    r.school,
    r.grade_level,
    r.graduation_year,
    r.ktc_cohort,
    r.year_in_network,
    r.iep_status,
    r.grad_iep_exempt_status_overall,
    r.cumulative_y1_gpa,
    r.cumulative_y1_gpa_projected,
    r.college_match_gpa,
    r.college_match_gpa_bands,
    max(r.ccr_teacher_name) as ccr_teacher_name,
    max(r.ccr_section) as ccr_section,
    max(r.psat89_count_lifetime) as psat89_count_lifetime,
    max(r.psat10_count_lifetime) as psat10_count_lifetime,
    max(r.psatnmsqt_count_lifetime) as psatnmsqt_count_lifetime,
    max(r.sat_count_lifetime) as sat_count_lifetime,
    max(r.sat_total_superscore) as sat_total_superscore,
    max(r.sat_ebrw_highest) as sat_ebrw_highest,
    max(r.sat_math_highest) as sat_math_highest,
    es.earliest_sat_total,
    lp.latest_psat_total,
    lp.psat_score_type as latest_psat_score_type,
    lp.psat_date as latest_psat_date,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Fall'
                and r.expected_grade_level = 12
            then r.score
        end
    ) as g12_sat_total_fall,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Fall'
                and r.expected_grade_level = 12
            then r.score
        end
    )
    - es.earliest_sat_total as g12_sat_total_fall_growth_from_first_sat,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Fall'
                and r.expected_grade_level = 12
            then r.score
        end
    )
    - lp.latest_psat_total as g12_sat_total_fall_growth_from_psat,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score_growth'
                and r.expected_admin_season = 'Fall'
                and r.expected_grade_level = 12
            then r.score
        end
    ) as g12_sat_total_growth_fall,
    max(
        case
            when
                r.expected_score_type = 'sat_ebrw'
                and r.expected_admin_season = 'Fall'
                and r.expected_grade_level = 12
            then r.score
        end
    ) as g12_sat_ebrw_fall,
    max(
        case
            when
                r.expected_score_type = 'sat_math'
                and r.expected_admin_season = 'Fall'
                and r.expected_grade_level = 12
            then r.score
        end
    ) as g12_sat_math_fall,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 12
            then r.score
        end
    ) as g12_sat_total_winter,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 12
            then r.score
        end
    )
    - es.earliest_sat_total as g12_sat_total_winter_growth_from_first_sat,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 12
            then r.score
        end
    )
    - lp.latest_psat_total as g12_sat_total_winter_growth_from_psat,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score_growth'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 12
            then r.score
        end
    ) as g12_sat_total_growth_winter,
    max(
        case
            when
                r.expected_score_type = 'sat_ebrw'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 12
            then r.score
        end
    ) as g12_sat_ebrw_winter,
    max(
        case
            when
                r.expected_score_type = 'sat_math'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 12
            then r.score
        end
    ) as g12_sat_math_winter,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 11
            then r.score
        end
    ) as g11_sat_total_winter,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 11
            then r.score
        end
    )
    - es.earliest_sat_total as g11_sat_total_winter_growth_from_first_sat,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 11
            then r.score
        end
    )
    - lp.latest_psat_total as g11_sat_total_winter_growth_from_psat,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score_growth'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 11
            then r.score
        end
    ) as g11_sat_total_growth_winter,
    max(
        case
            when
                r.expected_score_type = 'sat_ebrw'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 11
            then r.score
        end
    ) as g11_sat_ebrw_winter,
    max(
        case
            when
                r.expected_score_type = 'sat_math'
                and r.expected_admin_season = 'Winter'
                and r.expected_grade_level = 11
            then r.score
        end
    ) as g11_sat_math_winter,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Spring'
                and r.expected_grade_level = 11
            then r.score
        end
    ) as g11_sat_total_spring,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Spring'
                and r.expected_grade_level = 11
            then r.score
        end
    )
    - es.earliest_sat_total as g11_sat_total_spring_growth_from_first_sat,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score'
                and r.expected_admin_season = 'Spring'
                and r.expected_grade_level = 11
            then r.score
        end
    )
    - lp.latest_psat_total as g11_sat_total_spring_growth_from_psat,
    max(
        case
            when
                r.expected_score_type = 'sat_total_score_growth'
                and r.expected_admin_season = 'Spring'
                and r.expected_grade_level = 11
            then r.score
        end
    ) as g11_sat_total_growth_spring,
    max(
        case
            when
                r.expected_score_type = 'sat_ebrw'
                and r.expected_admin_season = 'Spring'
                and r.expected_grade_level = 11
            then r.score
        end
    ) as g11_sat_ebrw_spring,
    max(
        case
            when
                r.expected_score_type = 'sat_math'
                and r.expected_admin_season = 'Spring'
                and r.expected_grade_level = 11
            then r.score
        end
    ) as g11_sat_math_spring,
    max(
        case
            when
                r.expected_score_type = 'psatnmsqt_total'
                and r.expected_grade_level = 10
            then r.score
        end
    ) as g10_psatnmsqt_total,
    max(
        case
            when
                r.expected_score_type = 'psatnmsqt_ebrw' and r.expected_grade_level = 10
            then r.score
        end
    ) as g10_psatnmsqt_ebrw,
    max(
        case
            when
                r.expected_score_type = 'psatnmsqt_math_section'
                and r.expected_grade_level = 10
            then r.score
        end
    ) as g10_psatnmsqt_math,
    max(
        case
            when r.expected_score_type = 'psat10_total' and r.expected_grade_level = 10
            then r.score
        end
    ) as g10_psat10_total,
    max(
        case
            when r.expected_score_type = 'psat10_ebrw' and r.expected_grade_level = 10
            then r.score
        end
    ) as g10_psat10_ebrw,
    max(
        case
            when
                r.expected_score_type = 'psat10_math_section'
                and r.expected_grade_level = 10
            then r.score
        end
    ) as g10_psat10_math,
    max(
        case
            when r.expected_score_type = 'psat89_total' and r.expected_grade_level = 9
            then r.score
        end
    ) as g9_psat89_total,
    max(
        case
            when r.expected_score_type = 'psat89_ebrw' and r.expected_grade_level = 9
            then r.score
        end
    ) as g9_psat89_ebrw,
    max(
        case
            when
                r.expected_score_type = 'psat89_math_section'
                and r.expected_grade_level = 9
            then r.score
        end
    ) as g9_psat89_math,
    max(
        case
            when r.expected_score_type = 'psat10_total' and r.expected_grade_level = 10
            then r.score
        end
    ) - max(
        case
            when r.expected_score_type = 'psat89_total' and r.expected_grade_level = 9
            then r.score
        end
    ) as psat89_to_psat10_total_growth,
    max(
        case
            when r.expected_score_type = 'psat10_ebrw' and r.expected_grade_level = 10
            then r.score
        end
    ) - max(
        case
            when r.expected_score_type = 'psat89_ebrw' and r.expected_grade_level = 9
            then r.score
        end
    ) as psat89_to_psat10_ebrw_growth,
    max(
        case
            when
                r.expected_score_type = 'psat10_math_section'
                and r.expected_grade_level = 10
            then r.score
        end
    ) - max(
        case
            when
                r.expected_score_type = 'psat89_math_section'
                and r.expected_grade_level = 9
            then r.score
        end
    ) as psat89_to_psat10_math_growth
from roster as r
left join earliest_sat as es on r.student_number = es.student_number
left join latest_psat_before_first_sat as lp on r.student_number = lp.student_number
group by
    r.student_number,
    r.salesforce_id,
    r.student_name,
    r.student_first_name,
    r.student_last_name,
    r.student_email,
    r.region,
    r.school,
    r.grade_level,
    r.graduation_year,
    r.ktc_cohort,
    r.year_in_network,
    r.iep_status,
    r.grad_iep_exempt_status_overall,
    r.cumulative_y1_gpa,
    r.cumulative_y1_gpa_projected,
    r.college_match_gpa,
    r.college_match_gpa_bands,
    es.earliest_sat_total,
    lp.latest_psat_total,
    lp.psat_score_type,
    lp.psat_date
