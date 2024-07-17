with
    star_crosswalk as (
        select 'K' as grade, subject,
        from unnest(['SM', 'SEL']) as subject
        union all
        select grade, subject,
        from unnest(['1', '2']) as grade
        cross join unnest(['SM', 'SR']) as subject
    ),

    star as (
        select
            s.student_display_id,
            s.district_benchmark_proficient as star_is_proficient,
            safe_cast(left(s.school_year, 4) as numeric) as academic_year,
            safe_cast(if(s.grade = 'K', '0', s.grade) as numeric) as grade_level,
            if(s._dagster_partition_subject = 'SM', 'math', 'reading') as subject,
            row_number() over (
                partition by
                    s.student_display_id,
                    s._dagster_partition_subject,
                    s.school_year,
                    s.screening_period_window_name
                order by s.completed_date desc
            ) as rn_subj_round,
        from {{ ref("stg_renlearn__star") }} as s
        inner join
            star_crosswalk as c
            on s.grade = c.grade
            and s._dagster_partition_subject = c.subject
        where s.screening_period_window_name = 'Spring'
    ),

    criteria_union as (
        select
            academic_year_int as academic_year,
            concat('i-Ready ', lower(subject), ' typical growth') as measure,
            cast(if(student_grade = 'K', '0', student_grade) as string) as grade_level,
            round(
                avg(if(percent_progress_to_annual_typical_growth_percent >= 100, 1, 0)),
                2
            ) as criteria,
        from {{ ref("base_iready__diagnostic_results") }}
        where test_round = 'EOY' and rn_subj_round = 1 and region = 'KIPP Miami'
        group by academic_year_int, subject, student_grade

        union all

        select
            academic_year_int as academic_year,
            concat('i-Ready ', lower(subject), ' stretch growth') as measure,
            safe_cast(
                if(student_grade = 'K', '0', student_grade) as string
            ) as grade_level,
            round(
                avg(if(percent_progress_to_annual_stretch_growth_percent >= 100, 1, 0)),
                2
            ) as criteria,
        from {{ ref("base_iready__diagnostic_results") }}
        where test_round = 'EOY' and rn_subj_round = 1 and region = 'KIPP Miami'
        group by academic_year_int, subject, student_grade

        union all

        select
            academic_year,
            concat('FAST ', lower(assessment_subject), ' proficiency') as measure,
            cast(assessment_grade as string) as grade_level,
            round(avg(if(is_proficient, 1, 0)), 2) as criteria,
        from {{ ref("stg_fldoe__fast") }}
        where administration_window = 'PM3'
        group by academic_year, assessment_subject, assessment_grade

        union all

        select
            academic_year,
            concat('STAR ', subject, ' proficiency') as measure,
            cast(grade_level as string) as grade_level,
            round(avg(if(star_is_proficient = 'Yes', 1, 0)), 2) as criteria,
        from star
        where rn_subj_round = 1
        group by academic_year, subject, grade_level

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
            yearid + 1990 as academic_year,
            'fte2 enrollment' as measure,
            'region' as grade_level,
            sum(if(is_enrolled_fte2, 1, 0)) as criteria,
        from {{ ref("int_students__fldoe_fte") }}
        group by yearid

        union all

        select
            academic_year,
            'science assessment' as measure,
            cast(enrolled_grade as string) as grade_level,
            round(avg(if(is_proficient, 1, 0)), 2) as criteria,
        from {{ ref("stg_fldoe__science") }}
        group by academic_year, enrolled_grade

        union all

        select
            academic_year,
            concat(lower(test_name), ' eoc') as measure,
            cast(enrolled_grade as string) as grade_level,
            round(avg(if(is_proficient, 1, 0)), 2) as criteria,
        from {{ ref("stg_fldoe__eoc") }}
        where not is_invalidated
        group by academic_year, test_name, enrolled_grade
    )

select
    pc.academic_year,
    pc.group,
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
