with
    failing as (
        select
            fg.studentid,
            fg.yearid,
            fg.storecode,
            sum(
                case when fg.y1_grade_letter in ('F', 'F*') then 1 else 0 end
            ) as n_failing,
            sum(
                case
                    when
                        fg.y1_grade_letter in ('F', 'F*')
                        and c.credittype in ('MATH', 'ENG', 'SCI', 'SOC')
                    then 1
                    else 0
                end
            ) as n_failing_ms_core
        from powerschool.final_grades_static as fg
        inner join
            powerschool.courses as c
            on fg.course_number = c.course_number
            and fg.`db_name` = c.`db_name`
        group by fg.studentid, fg.yearid, fg.storecode
    ),

    credits as (
        select
            studentid,
            `db_name`,
            schoolid,
            earned_credits_cum,
            earned_credits_cum_projected
        from powerschool.gpa_cumulative
    ),

    enrolled_credits as (
        select student_number, academic_year, sum(credit_hours) as credit_hours_enrolled
        from powerschool.course_enrollments
        where
            course_enroll_status = 0 and section_enroll_status = 0 and rn_course_yr = 1
        group by student_number, academic_year
    ),

    agg_student_responses_all as (
        select
            local_student_id,
            academic_year,
            term_administered,
            avg(performance_band_number) as avg_performance_band_number
        from illuminate_dna_assessments.agg_student_responses_all
        where
            module_type like 'QA%'
            and subject_area in ('Mathematics', 'Algebra I')
            and response_type = 'O'
        group by local_student_id, academic_year, term_administered
    ),

    qas as (
        select
            local_student_id,
            academic_year,
            term_administered,
            avg_performance_band_number
        from agg_student_responses_all
    ),

    promo as (
        select
            co.student_number,
            co.studentid,
            co.`db_name`,
            co.academic_year,
            co.school_level,
            co.schoolid,
            co.grade_level,
            co.iep_status,
            case
                when co.is_retained_year + co.is_retained_ever >= 1 then 1 else 0
            end as is_retained_flag,

            s.sched_nextyeargrade,

            rt.time_per_name as reporting_term_name,
            rt.alt_name,
            rt.is_curterm,

            `ada`.ada_y1_running,

            lit.read_lvl as fp_independent_level,
            lit.goal_status as fp_goal_status,

            case
                when co.school_level = 'MS' then f.n_failing_ms_core else f.n_failing
            end as grades_y1_failing_projected,

            cr.earned_credits_cum_projected as grades_y1_credits_projected,

            isnull (cr.earned_credits_cum, 0)
            + isnull (enr.credit_hours_enrolled, 0) as grades_y1_credits_enrolled,

            case
                when co.grade_level = 9
                then 25
                when co.grade_level = 10
                then 50
                when co.grade_level = 11
                then 85
                when co.grade_level = 12
                then 120
            end as grades_y1_credits_goal,

            qas.avg_performance_band_number as qa_avg_performance_band_number,
        from powerschool.cohort_identifiers_static as co
        inner join powerschool.students as s on co.student_number = s.student_number
        inner join
            reporting.reporting_terms as rt
            on co.schoolid = rt.schoolid
            and co.academic_year = rt.academic_year
            and rt.identifier = 'RT'
            and rt._fivetran_deleted = 0
        left join
            `ada`
            on co.studentid = `ada`.studentid
            and co.`db_name` = `ada`.`db_name`
            and co.yearid = `ada`.yearid
        left join
            lit.achieved_by_round_static as lit
            on co.student_number = lit.student_number
            and co.academic_year = lit.academic_year
            and rt.alt_name = lit.test_round
        left join
            failing as f
            on co.studentid = f.studentid
            and co.yearid = f.yearid
            and rt.alt_name = f.storecode
        left join
            credits as cr
            on co.studentid = cr.studentid
            and co.schoolid = cr.schoolid
            and co.`db_name` = cr.`db_name`
        left join
            enrolled_credits as enr
            on co.student_number = enr.student_number
            and co.academic_year = enr.academic_year
        left join
            qas
            on co.student_number = qas.local_student_id
            and co.academic_year = qas.academic_year
            and rt.alt_name = qas.term_administered
        where co.rn_year = 1
    ),

    promo2 as (
        select
            student_number,
            studentid,
            `db_name`,
            academic_year,
            school_level,
            schoolid,
            grade_level,
            iep_status,
            is_retained_flag,
            sched_nextyeargrade,
            reporting_term_name,
            alt_name,
            is_curterm,
            ada_y1_running,
            fp_independent_level,
            grades_y1_failing_projected,
            grades_y1_credits_projected,
            grades_y1_credits_enrolled,
            grades_y1_credits_goal,
            qa_avg_performance_band_number,
            case
                when ada_y1_running >= 90.1
                then 'On Track'
                when ada_y1_running < 90.1
                then 'Off Track'
                when ada_y1_running < 80.0
                then 'At Risk'
                else 'No Data'
            end as promo_status_attendance,
            case
                when school_level in ('HS', 'MS')
                then 'N/A'
                when fp_goal_status in ('Target', 'Above Target', 'Achieved Z')
                then 'On Track'
                when fp_goal_status in ('Below', 'Approaching')
                then 'Off Track'
                when fp_goal_status = 'Far Below'
                then 'At Risk'
                else 'No Data'
            end as promo_status_lit,
            case
                when school_level in ('HS', 'MS')
                then 'N/A'
                when qa_avg_performance_band_number >= 4
                then 'On Track'
                when qa_avg_performance_band_number in (2, 3)
                then 'Off Track'
                when qa_avg_performance_band_number = 1
                then 'At Risk'
                else 'No Data'
            end as promo_status_qa_math,
            case
                when school_level = 'ES'
                then 'N/A'
                when school_level = 'MS'
                then
                    case
                        when grades_y1_failing_projected = 0
                        then 'On Track'
                        when grades_y1_failing_projected >= 1
                        then 'Off Track'
                        when grades_y1_failing_projected >= 2
                        then 'At Risk'
                        else 'No Data'
                    end
                when school_level = 'HS'
                then
                    case
                        when grades_y1_credits_projected >= grades_y1_credits_goal
                        then 'On Track'
                        when grades_y1_credits_projected < grades_y1_credits_goal
                        then 'Off Track'
                        else 'No Data'
                    end
            end as promo_status_grades
        from promo
    ),

    promo3 as (
        select
            student_number,
            studentid,
            `db_name`,
            academic_year,
            schoolid,
            iep_status,
            is_retained_flag,
            reporting_term_name,
            alt_name,
            is_curterm,
            ada_y1_running,
            fp_independent_level,
            grades_y1_failing_projected,
            grades_y1_credits_projected,
            grades_y1_credits_enrolled,
            grades_y1_credits_goal,
            qa_avg_performance_band_number,
            promo_status_attendance,
            promo_status_lit,
            promo_status_grades,
            promo_status_qa_math,
            case
                when alt_name = 'Q4'
                then
                    case
                        when sched_nextyeargrade = 99 and school_level = 'HS'
                        then 'Graduated'
                        when sched_nextyeargrade > grade_level
                        then 'Promoted'
                        when sched_nextyeargrade <= grade_level
                        then 'Retained'
                    end
                when
                    school_level != 'HS'
                    and (iep_status = 'SPED' or is_retained_flag = 1)
                then 'See Teacher'
                when school_level = 'HS'
                then 'N/A'
                when
                    concat(
                        promo_status_attendance,
                        promo_status_lit,
                        promo_status_grades,
                        promo_status_qa_math
                    )
                    like '%At Risk%'
                then 'At Risk'
                when
                    concat(
                        promo_status_attendance,
                        promo_status_lit,
                        promo_status_grades,
                        promo_status_qa_math
                    )
                    like '%Off Track%'
                then 'Off Track'
                else 'On Track'
            end as promo_status_overall,
        from promo2
    )

select
    ps.student_number,
    ps.academic_year,
    ps.alt_name as term,
    ps.promo_status_overall,
    ps.promo_status_attendance,
    ps.promo_status_lit,
    ps.promo_status_grades,
    ps.promo_status_qa_math,
    ps.grades_y1_credits_projected,
    ps.grades_y1_credits_enrolled,
    ps.grades_y1_failing_projected,

    gpa.gpa_term as gpa_term,
    gpa.gpa_y1 as gpa_y1,

    cum.cumulative_y1_gpa as gpa_cum,
    cum.cumulative_y1_gpa_projected as gpa_cum_projected,
from promo3 as ps
left join
    powerschool.gpa_detail as gpa
    on ps.student_number = gpa.student_number
    and ps.academic_year = gpa.academic_year
    and ps.alt_name = gpa.term_name
left join
    powerschool.gpa_cumulative as cum
    on ps.studentid = cum.studentid
    and ps.schoolid = cum.schoolid
    and ps.`db_name` = cum.`db_name`
where ps.academic_year = utilities.global_academic_year()
