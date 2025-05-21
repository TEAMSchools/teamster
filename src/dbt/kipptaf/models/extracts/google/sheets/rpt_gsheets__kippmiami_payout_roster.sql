with
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
            round(
                avg(
                    if(
                        grade_level = 0,
                        is_district_benchmark_proficient_int,
                        is_state_benchmark_proficient_int
                    )
                ),
                2
            ) as criteria,
        from {{ ref("int_renlearn__star_rollup") }}
        where screening_period_window_name = 'Spring' and rn_subj_round = 1
        group by academic_year, star_discipline, grade_level

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
        group by academic_year, assessment_name, assessment_subject, assessment_grade

        union all

        select
            fl.academic_year,
            concat(fl.assessment_subject, ' growth') as measure,
            fl.assessment_grade,
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
            mclass_academic_year as academic_year,
            'DIBELS EOY composite' as measure,
            cast(mclass_assessment_grade_int as string) as grade_level,
            round(
                avg(
                    case
                        when eoy_composite in ('Above Benchmark', 'At Benchmark')
                        then 1
                        when eoy_composite not in ('Above Benchmark', 'At Benchmark')
                        then 0
                    end
                ),
                2
            ) as criteria,
        from {{ ref("int_amplify__all_assessments") }}
        where mclass_measure_standard = 'Composite'
        group by mclass_academic_year, mclass_assessment_grade_int

        union all

        select
            co.academic_year,
            'Grade 3 promotion' as measure,
            cast(co.grade_level as string) as grade_level,
            round(
                avg(if(co.is_retained_year or fl.achievement_level_int > 1, 1, 0)), 2
            ) as criteria,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("int_fldoe__all_assessments") }} as fl
            on co.fleid = fl.student_id
            and co.academic_year = fl.academic_year
            and fl.assessment_name = 'FAST'
            and fl.assessment_subject = 'English Language Arts'
            and fl.administration_window = 'PM3'
        where co.rn_year = 1 and co.grade_level = 3
        group by co.academic_year, co.grade_level
    )

select
    pc.academic_year,
    pc.criteria_group as `group`,
    pc.grade_level,
    pc.measure,
    pc.criteria as criteria_cutoff,
    pc.payout_amount as payout_potential,

    cu.criteria as criteria_actual,

    if(cu.criteria >= pc.criteria, pc.payout_amount, 0) as payout_actual,
from {{ ref("stg_people__miami_performance_criteria") }} as pc
left join
    criteria_union as cu
    on pc.academic_year = cu.academic_year
    and pc.grade_level = cu.grade_level
    and pc.measure = cu.measure
where pc.academic_year is not null
