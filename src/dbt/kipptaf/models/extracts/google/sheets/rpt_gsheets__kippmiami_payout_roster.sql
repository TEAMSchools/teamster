with
    school_grade_cw as (
        select 'Royalty' as school, grade_level,
        from unnest(['0', '1', '2', '3', '4']) as grade_level

        union all

        select 'Courage' as school, grade_level,
        from unnest(['5', '6', '7', '8']) as grade_level
    ),

    criteria_union as (
        select
            academic_year_int as academic_year,

            concat('i-Ready ', lower(`subject`), ' typical growth') as measure,

            cast(if(student_grade = 'K', '0', student_grade) as string) as grade_level,

            round(
                avg(if(percent_progress_to_annual_typical_growth_percent >= 100, 1, 0)),
                2
            ) as criteria,
        from {{ ref("base_iready__diagnostic_results") }}
        where test_round = 'EOY' and rn_subj_round = 1 and region = 'KIPP Miami'
        group by academic_year_int, `subject`, student_grade

        union all

        select
            academic_year_int as academic_year,

            concat('i-Ready ', lower(`subject`), ' stretch growth') as measure,

            safe_cast(
                if(student_grade = 'K', '0', student_grade) as string
            ) as grade_level,

            round(
                avg(if(percent_progress_to_annual_stretch_growth_percent >= 100, 1, 0)),
                2
            ) as criteria,
        from {{ ref("base_iready__diagnostic_results") }}
        where test_round = 'EOY' and rn_subj_round = 1 and region = 'KIPP Miami'
        group by academic_year_int, `subject`, student_grade

        union all

        select
            academic_year,
            concat('STAR ', star_discipline, ' proficiency') as measure,
            cast(grade_level as string) as grade_level,
            round(avg(is_district_benchmark_proficient_int), 2) as criteria,
        from {{ ref("int_renlearn__star_rollup") }}
        where screening_period_window_name = 'Spring' and rn_subj_round = 1
        group by academic_year, star_discipline, grade_level

        union all

        select
            academic_year,
            concat('STAR ', star_discipline, ' proficiency') as measure,
            'Royalty' as grade_level,
            round(avg(is_district_benchmark_proficient_int), 2) as criteria,
        from {{ ref("int_renlearn__star_rollup") }}
        where screening_period_window_name = 'Spring' and rn_subj_round = 1
        group by academic_year, star_discipline

        union all

        select
            co.academic_year,

            'ada' as measure,

            cast(co.grade_level as string) as grade_level,

            round(avg(ada.ada), 2) as criteria,
        from {{ ref("int_powerschool__ada") }} as ada
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on ada.studentid = co.studentid
            and ada.yearid = co.yearid
            and co.region = 'Miami'
            and co.grade_level != 99
            and co.rn_year = 1
        group by co.academic_year, co.grade_level

        union all

        select
            co.academic_year,

            'ada' as measure,

            co.school_name as grade_level,

            round(avg(ada.ada), 2) as criteria,
        from {{ ref("int_powerschool__ada") }} as ada
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on ada.studentid = co.studentid
            and ada.yearid = co.yearid
            and co.region = 'Miami'
            and co.grade_level != 99
            and co.rn_year = 1
        group by co.academic_year, co.school_name

        union all

        select
            co.academic_year,
            'ada' as measure,
            'region' as grade_level,
            round(avg(ada.ada), 2) as criteria,
        from {{ ref("int_powerschool__ada") }} as ada
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on ada.studentid = co.studentid
            and ada.yearid = co.yearid
            and co.region = 'Miami'
            and co.grade_level != 99
            and co.rn_year = 1
        group by co.academic_year

        union all

        select
            academic_year,
            'fte2 enrollment' as measure,
            'region' as grade_level,
            sum(if(is_fldoe_fte_2, 1, 0)) as criteria,
        from {{ ref("base_powerschool__student_enrollments") }}
        where region = 'Miami' and rn_year = 1 and grade_level != 99
        group by academic_year

        union all

        select
            academic_year,
            if(
                assessment_subject = 'Science',
                'Science proficiency',
                concat(assessment_name, ' ', assessment_subject, ' proficiency')
            ) as measure,
            cast(assessment_grade as string) as grade_level,
            round(avg(if(is_proficient, 1, 0)), 2) as criteria,
        from {{ ref("int_fldoe__all_assessments") }}
        where administration_window = 'PM3'
        group by academic_year, assessment_name, assessment_subject, assessment_grade

        union all

        select
            fl.academic_year,
            concat('FAST ', fl.assessment_subject, ' proficiency') as measure,
            gs.school as grade_level,
            round(avg(if(fl.is_proficient, 1, 0)), 2) as criteria,
        from {{ ref("int_fldoe__all_assessments") }} as fl
        inner join school_grade_cw as gs on fl.assessment_grade = gs.grade_level
        where fl.administration_window = 'PM3' and fl.assessment_name = 'FAST'
        group by fl.academic_year, fl.assessment_subject, gs.school

        union all

        select
            fl.academic_year,
            concat('FAST ', fl.assessment_subject, ' disparity') as measure,
            'region' as grade_level,
            1 - round(
                avg(
                    case
                        when co.spedlep not like 'SPED%' and fl.is_proficient
                        then 1
                        when co.spedlep not like 'SPED%' and not fl.is_proficient
                        then 0
                    end
                ) - avg(
                    case
                        when co.spedlep like 'SPED%' and fl.is_proficient
                        then 1
                        when co.spedlep like 'SPED%' and not fl.is_proficient
                        then 0
                    end
                ),
                2
            ) as criteria,
        from {{ ref("int_fldoe__all_assessments") }} as fl
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on fl.academic_year = co.academic_year
            and fl.student_id = co.fleid
            and co.rn_year = 1
        where fl.administration_window = 'PM3' and fl.assessment_name = 'FAST'
        group by fl.academic_year, fl.assessment_subject

        union all

        select
            fl.academic_year,
            concat(fl.assessment_subject, ' growth') as measure,
            fl.assessment_grade as grade_level,
            round(
                avg(
                    case
                        when
                            py.prev_pm3_scale is not null
                            and fl.sublevel_number > py.prev_pm3_sublevel_number
                        then 1
                        when py.prev_pm3_scale is not null and fl.sublevel_number = 8
                        then 1
                        when
                            py.prev_pm3_scale is not null
                            and py.prev_pm3_sublevel_number in (6, 7)
                            and py.prev_pm3_sublevel_number = fl.sublevel_number
                            and fl.scale_score > py.prev_pm3_scale
                        then 1
                        when py.prev_pm3_scale is not null
                        then 0
                    end
                ),
                2
            ) as criteria,
        from {{ ref("int_fldoe__all_assessments") }} as fl
        left join
            {{ ref("int_assessments__fast_previous_year") }} as py
            on fl.student_id = py.student_id
            and fl.assessment_subject = py.assessment_subject
            and fl.academic_year = py.academic_year
        where fl.assessment_name = 'FAST' and fl.administration_window = 'PM3'
        group by fl.academic_year, fl.assessment_subject, fl.assessment_grade

        union all

        select
            fl.academic_year,
            concat(fl.assessment_subject, ' growth - IEP') as measure,
            co.school_abbreviation as grade_level,
            round(
                avg(
                    case
                        when
                            py.prev_pm3_scale is not null
                            and fl.sublevel_number > py.prev_pm3_sublevel_number
                        then 1
                        when py.prev_pm3_scale is not null and fl.sublevel_number = 8
                        then 1
                        when
                            py.prev_pm3_scale is not null
                            and py.prev_pm3_sublevel_number in (6, 7)
                            and py.prev_pm3_sublevel_number = fl.sublevel_number
                            and fl.scale_score > py.prev_pm3_scale
                        then 1
                        when py.prev_pm3_scale is not null
                        then 0
                    end
                ),
                2
            ) as criteria,
        from {{ ref("int_fldoe__all_assessments") }} as fl
        left join
            {{ ref("int_assessments__fast_previous_year") }} as py
            on fl.student_id = py.student_id
            and fl.assessment_subject = py.assessment_subject
            and fl.academic_year = py.academic_year
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on fl.academic_year = co.academic_year
            and fl.student_id = co.fleid
            and co.spedlep like 'SPED%'
            and co.rn_year = 1
        where fl.assessment_name = 'FAST' and fl.administration_window = 'PM3'
        group by fl.academic_year, fl.assessment_subject, co.school_abbreviation

        union all

        select
            fl.academic_year,
            concat(fl.assessment_subject, ' growth - IEP') as measure,
            'region' as grade_level,
            round(
                avg(
                    case
                        when
                            py.prev_pm3_scale is not null
                            and fl.sublevel_number > py.prev_pm3_sublevel_number
                        then 1
                        when py.prev_pm3_scale is not null and fl.sublevel_number = 8
                        then 1
                        when
                            py.prev_pm3_scale is not null
                            and py.prev_pm3_sublevel_number in (6, 7)
                            and py.prev_pm3_sublevel_number = fl.sublevel_number
                            and fl.scale_score > py.prev_pm3_scale
                        then 1
                        when py.prev_pm3_scale is not null
                        then 0
                    end
                ),
                2
            ) as criteria,
        from {{ ref("int_fldoe__all_assessments") }} as fl
        left join
            {{ ref("int_assessments__fast_previous_year") }} as py
            on fl.student_id = py.student_id
            and fl.assessment_subject = py.assessment_subject
            and fl.academic_year = py.academic_year
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on fl.academic_year = co.academic_year
            and fl.student_id = co.fleid
            and co.spedlep like 'SPED%'
            and co.rn_year = 1
        where fl.assessment_name = 'FAST' and fl.administration_window = 'PM3'
        group by fl.academic_year, fl.assessment_subject

        union all

        select
            amp.academic_year,
            'DIBELS EOY composite' as measure,
            cast(amp.assessment_grade_int as string) as grade_level,
            round(
                avg(
                    case
                        when amp.eoy_composite in ('Above Benchmark', 'At Benchmark')
                        then 1
                        when
                            amp.eoy_composite not in ('Above Benchmark', 'At Benchmark')
                        then 0
                    end
                ),
                2
            ) as criteria,
        from {{ ref("int_amplify__all_assessments") }} as amp
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on amp.student_number = s.student_number
            and s.enroll_status = 0
            and regexp_extract(s._dbt_source_relation, r'(kipp\w+)_') = 'kippmiami'
        where amp.measure_standard = 'Composite' and amp.academic_year = 2024
        group by amp.academic_year, amp.assessment_grade_int

        union all

        select
            co.academic_year,
            'Grade 3 promotion' as measure,
            cast(co.grade_level as string) as grade_level,
            round(
                avg(if(co.is_retained_year or fl.achievement_level_int > 1, 1, 0)), 2
            ) as criteria,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        left join
            {{ ref("int_fldoe__all_assessments") }} as fl
            on co.fleid = fl.student_id
            and co.academic_year = fl.academic_year
            and fl.assessment_name = 'FAST'
            and fl.assessment_subject = 'English Language Arts'
            and fl.administration_window = 'PM3'
        where
            co.rn_year = 1
            and co.grade_level = 3
            and co.enroll_status = 0
            and co.region = 'Miami'
        group by co.academic_year, co.grade_level
    ),

    criteria_eval as (
        select
            pc.academic_year,
            pc.criteria_group as `group`,
            pc.grade_level,
            pc.measure,
            pc.criteria as criteria_cutoff,
            pc.payout_amount as payout_potential,
            pc.grouped_measure,

            cu.criteria as criteria_actual,

            if(cu.criteria >= pc.criteria, true, false) as is_met_criteria,
        -- if(cu.criteria >= pc.criteria, pc.payout_amount, 0) as payout_actual,
        from {{ ref("stg_people__miami_performance_criteria") }} as pc
        left join
            criteria_union as cu
            on pc.academic_year = cu.academic_year
            and pc.grade_level = cu.grade_level
            and pc.measure = cu.measure
        where pc.academic_year is not null
    ),

    criteria_grouped as (
        select
            academic_year,
            `group`,
            grade_level,
            grouped_measure,

            string_agg(
                format(
                    '%s: %.2f/%.2f (%s)',
                    measure,
                    criteria_actual,
                    criteria_cutoff,
                    if(criteria_actual >= criteria_cutoff, 'Pass', 'Fail')
                ),
                '; '
            ) as criteria_summary,
            string_agg(measure, ', ') as measures,
            max(payout_potential) as payout_potential,
            min(is_met_criteria) as is_met_criteria,
        from criteria_eval
        group by academic_year, `group`, grade_level, grouped_measure
    )

select
    academic_year,
    `group`,
    grade_level,
    criteria_summary,
    measures,
    grouped_measure,
    payout_potential,
    if(is_met_criteria, payout_potential, 0) as payout_actual,
from criteria_grouped
