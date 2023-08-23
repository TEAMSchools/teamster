/*{% set periods = ["BOY", "BOY->MOY", "MOY", "MOY->EOY", "EOY"] %}

with
    union_relations as (
        select
            bss.surrogate_key,
            bss.student_primary_id,
            bss.academic_year,
            bss.benchmark_period as period,
            bss.client_date,
            bss.sync_date,
            bss.reporting_class_id,
            bss.reporting_class_name,
            bss.assessing_teacher_staff_id,
            bss.assessing_teacher_name,
            bss.official_teacher_staff_id,
            bss.official_teacher_name,
            bss.assessment_grade,

            u.measure,
            u.score,
            u.level,
            u.national_norm_percentile,
            u.semester_growth,
            u.year_growth,

            null as score_change,
            null as probe_number,
            null as total_number_of_probes,

            'benchmark' as assessment_type,
        from {{ ref("stg_amplify__benchmark_student_summary") }} as bss
        inner join
            {{ ref("int_amplify__benchmark_student_summary_unpivot") }} as u
            on bss.surrogate_key = u.surrogate_key

        union all

        select
            surrogate_key,
            student_primary_id,
            academic_year,
            pm_period as period,
            client_date,
            sync_date,
            reporting_class_id,
            reporting_class_name,
            assessing_teacher_staff_id,
            assessing_teacher_name,
            official_teacher_staff_id,
            official_teacher_name,
            assessment_grade,
            measure,
            score,
            null as level,
            null as percentile,
            null as semester_growth,
            null as year_growth,
            score_change,
            probe_number,
            total_number_of_probes,

            'pm' as assessment_type,
        from {{ ref("stg_amplify__pm_student_summary") }}
    ),

    student_schedule_test as (
        select
            se.student_number,
            se.first_name,
            se.last_name,
            se.lastfirst,
            se.academic_year,
            se.region,
            se.school_level,
            se.schoolid,
            se.school_name,
            se.school_abbreviation,
            se.grade_level,
            se.gender,
            se.ethnicity,
            se.lunch_status,
            se.is_out_of_district,
            se.is_homeless,
            se.is_504,
            se.lep_status as is_lep,
            if(spedlep = 'no iep' or se.spedlep is null, false, true) as is_sped,

            ce.cc_course_number as course_number,
            ce.cc_section_number as section_number,
            ce.cc_teacherid as teacher_id,
            ce.courses_course_name as course_name,
            ce.teachernumber as teacher_number,
            ce.teacher_lastfirst as teacher_name,
            if(ce.cc_studentid is null, true, false) as enrolled_but_not_scheduled,

            period,
        from {{ ref("base_powerschool__student_enrollments") }} as se
        left join
            {{ ref("base_powerschool__course_enrollments") }} as ce
            on se.studentid = ce.cc_studentid
            and se.yearid = ce.cc_yearid
            and ce.rn_course_number_year = 1
            and not ce.is_dropped_section
            and ce.courses_course_name
            in ('ela grK', 'ela K', 'ela gr1', 'ela gr2', 'ela gr3', 'ela gr4')
        cross join unnest({{ periods }}) as period
        where se.rn_year = 1 and se.academic_year >= 2022 and se.grade_level <= 4
    ),

    student_data as (
        select
            s.student_number,
            s.lastfirst,
            s.last_name,
            s.first_name,
            s.academic_year,
            s.region,
            s.school_level,
            s.schoolid,
            s.school_name,
            s.school_abbreviation,
            s.grade_level,
            s.gender,
            s.ethnicity,
            s.lunch_status,
            s.is_out_of_district,
            s.is_sped,
            s.is_504,
            s.is_lep,
            s.is_homeless,
            s.teacher_id,
            s.teacher_name,
            s.course_number,
            s.course_name,
            s.section_number,
            s.period,

            -- tagging students as enrolled in school but not scheduled for the course
            -- that would allow them to take the diBels test
            d.assessment_type,
            d.client_date,
            d.sync_date,
            d.reporting_class_id,
            d.reporting_class_name,
            d.assessment_grade,
            d.assessing_teacher_staff_id,
            d.assessing_teacher_name,
            d.official_teacher_staff_id,
            d.official_teacher_name,
            d.measure,
            d.score,
            d.level,
            d.national_norm_percentile,
            d.semester_growth,
            d.year_growth,
            d.score_change,
            d.probe_number,
            d.total_number_of_probes,
            if(
                d.student_primary_id is not null, true, false
            ) as student_has_assessment_data,

            'Kipp nJ/miami' as district,
        from student_schedule_test as s
        left join
            union_relations as d
            on s.student_number = d.student_primary_id
            and s.academic_year = d.academic_year
            and s.period = d.period
    ),

    with_counts as (
        select
            *,

            -- participation rates by school_course_section
            count(distinct student_number) over (
                partition by
                    academic_year, schoolid, course_name, section_number, period
            )
            as participation_school_course_section_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by
                    academic_year, course_name, section_number, schoolid, period
            )
            as participation_school_course_section_bm_pm_period_total_students_enrolled,

            -- participation rates by school_course
            count(distinct student_number) over (
                partition by academic_year, schoolid, course_name, period
            ) as participation_school_course_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, schoolid, course_name, period
            ) as participation_school_course_bm_pm_period_total_students_enrolled,

            -- participation rates by school_grade
            count(distinct student_number) over (
                partition by academic_year, schoolid, grade_level, period
            ) as participation_school_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, schoolid, grade_level, period
            ) as participation_school_grade_bm_pm_period_total_students_enrolled,

            -- participation rates by school
            count(distinct student_number) over (
                partition by academic_year, schoolid, period
            ) as participation_school_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, schoolid, period
            ) as participation_school_bm_pm_period_total_students_enrolled,

            -- participation rates by region_grade
            count(distinct student_number) over (
                partition by academic_year, region, grade_level, period
            ) as participation_region_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, region, grade_level, period
            ) as participation_region_grade_bm_pm_period_total_students_enrolled,

            -- participation rates by region
            count(distinct student_number) over (
                partition by academic_year, region, period
            ) as participation_region_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, region, period
            ) as participation_region_bm_pm_period_total_students_enrolled,

            -- participation rates by district_grade
            count(distinct student_number) over (
                partition by academic_year, district, period
            ) as participation_district_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, district, period
            ) as participation_district_grade_bm_pm_period_total_students_enrolled,

            -- participation rates by district
            count(distinct student_number) over (
                partition by academic_year, district, period
            ) as participation_district_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, district, period
            ) as participation_district_bm_pm_period_total_students_enrolled,

            -- measure score met rates by school_course_section
            count(distinct student_number) over (
                partition by
                    academic_year,
                    schoolid,
                    course_name,
                    section_number,
                    period,
                    measure,
                    score
            )
            as measure_score_met_school_course_section_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by
                    academic_year,
                    schoolid,
                    course_name,
                    section_number,
                    period,
                    measure
            )
            as measure_score_met_school_course_section_bm_pm_period_total_students_enrolled,

            -- measure score met rates by school_course
            count(distinct student_number) over (
                partition by
                    academic_year, schoolid, course_name, period, measure, score
            )
            as measure_score_met_school_course_course_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, schoolid, course_name, period, measure
            ) as measure_score_met_school_course_bm_pm_period_total_students_enrolled,

            -- measure score met rates by school_grade
            count(distinct student_number) over (
                partition by
                    academic_year, schoolid, grade_level, period, measure, score
            ) as measure_score_met_school_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, schoolid, grade_level, period, measure
            ) as measure_score_met_school_grade_bm_pm_period_total_students_enrolled,

            -- measure score met rates by school
            count(distinct student_number) over (
                partition by academic_year, schoolid, period, measure, score
            ) as measure_score_met_school_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, schoolid, period, measure
            ) as measure_score_met_school_bm_pm_period_total_students_enrolled,

            -- measure score met rates by region_grade
            count(distinct student_number) over (
                partition by academic_year, region, grade_level, period, measure, score
            ) as measure_score_met_region_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, region, grade_level, period, measure
            ) as measure_score_met_region_grade_bm_pm_period_total_students_enrolled,

            -- measure score met rates by region
            count(distinct student_number) over (
                partition by academic_year, region, period, measure, score
            ) as measure_score_met_region_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, region, period, measure
            ) as measure_score_met_region_bm_pm_period_total_students_enrolled,

            -- measure score met rates by district_grade
            count(distinct student_number) over (
                partition by academic_year, district, period, measure, score
            ) as measure_score_met_district_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, district, period, measure
            ) as measure_score_met_district_grade_bm_pm_period_total_students_enrolled,

            -- measure score met rates by district
            count(distinct student_number) over (
                partition by academic_year, district, period, measure, score
            ) as measure_score_met_district_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, district, period, measure
            ) as measure_score_met_district_bm_pm_period_total_students_enrolled,

            -- measure level met rates by school_course_section
            count(distinct student_number) over (
                partition by
                    academic_year,
                    schoolid,
                    course_name,
                    section_number,
                    period,
                    measure,
                    level
            )
            as measure_level_met_school_course_section_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by
                    academic_year,
                    schoolid,
                    course_name,
                    section_number,
                    period,
                    measure
            )
            as measure_level_met_school_course_section_bm_pm_period_total_students_enrolled,

            -- measure level met rates by school_course
            count(distinct student_number) over (
                partition by
                    academic_year, schoolid, course_name, period, measure, level
            )
            as measure_level_met_school_course_course_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, schoolid, course_name, period, measure
            ) as measure_level_met_school_course_bm_pm_period_total_students_enrolled,

            -- measure level met rates by school_grade
            count(distinct student_number) over (
                partition by
                    academic_year, schoolid, grade_level, period, measure, level
            ) as measure_level_met_school_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, schoolid, grade_level, period, measure
            ) as measure_level_met_school_grade_bm_pm_period_total_students_enrolled,

            -- measure level met rates by school
            count(distinct student_number) over (
                partition by academic_year, schoolid, period, measure, level
            ) as measure_level_met_school_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, schoolid, period, measure
            ) as measure_level_met_school_bm_pm_period_total_students_enrolled,

            -- measure level met rates by region_grade
            count(distinct student_number) over (
                partition by academic_year, region, grade_level, period, measure, level
            ) as measure_level_met_region_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, region, grade_level, period, measure
            ) as measure_level_met_region_grade_bm_pm_period_total_students_enrolled,

            -- measure level met rates by region
            count(distinct student_number) over (
                partition by academic_year, region, period, measure, level
            ) as measure_level_met_region_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, region, period, measure
            ) as measure_level_met_region_bm_pm_period_total_students_enrolled,

            -- measure level met rates by district_grade
            count(distinct student_number) over (
                partition by academic_year, district, period, measure, level
            ) as measure_level_met_district_grade_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, district, period, measure
            ) as measure_level_met_district_grade_bm_pm_period_total_students_enrolled,

            -- measure level met rates by district
            count(distinct student_number) over (
                partition by academic_year, district, period, measure, level
            ) as measure_level_met_district_bm_pm_period_total_students_assessed,
            count(distinct student_number) over (
                partition by academic_year, district, period, measure
            ) as measure_level_met_district_bm_pm_period_total_students_enrolled,
        from student_data
    )

select
    *,
    safe_divide(
        participation_school_course_section_bm_pm_period_total_students_assessed,
        participation_school_course_section_bm_pm_period_total_students_enrolled
    ) as participation_school_course_section_bm_pm_period_percent,
    safe_divide(
        participation_school_course_bm_pm_period_total_students_assessed,
        participation_school_course_bm_pm_period_total_students_enrolled
    ) as participation_school_course_bm_pm_period_percent,
    safe_divide(
        participation_school_grade_bm_pm_period_total_students_assessed,
        participation_school_grade_bm_pm_period_total_students_enrolled
    ) as participation_school_grade_bm_pm_period_percent,
    safe_divide(
        participation_school_bm_pm_period_total_students_assessed,
        participation_school_bm_pm_period_total_students_enrolled
    ) as participation_school_bm_pm_period_percent,
    safe_divide(
        participation_region_grade_bm_pm_period_total_students_assessed,
        participation_region_grade_bm_pm_period_total_students_enrolled
    ) as participation_region_grade_bm_pm_period_percent,
    safe_divide(
        participation_region_bm_pm_period_total_students_assessed,
        participation_region_bm_pm_period_total_students_enrolled
    ) as participation_region_bm_pm_period_percent,
    safe_divide(
        participation_district_grade_bm_pm_period_total_students_assessed,
        participation_district_grade_bm_pm_period_total_students_enrolled
    ) as participation_district_grade_bm_pm_period_percent,
    safe_divide(
        participation_district_bm_pm_period_total_students_assessed,
        participation_district_bm_pm_period_total_students_enrolled
    ) as participation_district_bm_pm_period_percent,
    safe_divide(
        measure_score_met_school_course_section_bm_pm_period_total_students_assessed,
        measure_score_met_school_course_section_bm_pm_period_total_students_enrolled
    ) as measure_score_met_school_course_section_bm_pm_period_percent,
    safe_divide(
        measure_score_met_school_course_course_bm_pm_period_total_students_assessed,
        measure_score_met_school_course_bm_pm_period_total_students_enrolled
    ) as measure_score_met_school_course_bm_pm_period_percent,
    safe_divide(
        measure_score_met_school_grade_bm_pm_period_total_students_assessed,
        measure_score_met_school_grade_bm_pm_period_total_students_enrolled
    ) as measure_score_met_school_grade_bm_pm_period_percent,
    safe_divide(
        measure_score_met_school_bm_pm_period_total_students_assessed,
        measure_score_met_school_bm_pm_period_total_students_enrolled
    ) as measure_score_met_school_bm_pm_period_percent,
    safe_divide(
        measure_score_met_region_grade_bm_pm_period_total_students_assessed,
        measure_score_met_region_grade_bm_pm_period_total_students_enrolled
    ) as measure_score_met_region_grade_bm_pm_period_percent,
    safe_divide(
        measure_score_met_region_bm_pm_period_total_students_assessed,
        measure_score_met_region_bm_pm_period_total_students_enrolled
    ) as measure_score_met_region_bm_pm_period_percent,
    safe_divide(
        measure_score_met_district_grade_bm_pm_period_total_students_assessed,
        measure_score_met_district_grade_bm_pm_period_total_students_enrolled
    ) as measure_score_met_district_grade_bm_pm_period_percent_met,
    safe_divide(
        measure_score_met_district_bm_pm_period_total_students_assessed,
        measure_score_met_district_bm_pm_period_total_students_enrolled
    ) as measure_score_met_district_bm_pm_period_percent,
    safe_divide(
        measure_level_met_school_course_section_bm_pm_period_total_students_assessed,
        measure_level_met_school_course_section_bm_pm_period_total_students_enrolled
    ) as measure_level_met_school_course_section_bm_pm_period_percent,
    safe_divide(
        measure_level_met_school_course_course_bm_pm_period_total_students_assessed,
        measure_level_met_school_course_bm_pm_period_total_students_enrolled
    ) as measure_level_met_school_course_bm_pm_period_percent,
    safe_divide(
        measure_level_met_school_grade_bm_pm_period_total_students_assessed,
        measure_level_met_school_grade_bm_pm_period_total_students_enrolled
    ) as measure_level_met_school_grade_bm_pm_period_percent,
    safe_divide(
        measure_level_met_school_bm_pm_period_total_students_assessed,
        measure_level_met_school_bm_pm_period_total_students_enrolled
    ) as measure_level_met_school_bm_pm_period_percent,
    safe_divide(
        measure_level_met_region_grade_bm_pm_period_total_students_assessed,
        measure_level_met_region_grade_bm_pm_period_total_students_enrolled
    ) as measure_level_met_region_grade_bm_pm_period_percent,
    safe_divide(
        measure_level_met_region_bm_pm_period_total_students_assessed,
        measure_level_met_region_bm_pm_period_total_students_enrolled
    ) as measure_level_met_region_bm_pm_period_percent,
    safe_divide(
        measure_level_met_district_grade_bm_pm_period_total_students_assessed,
        measure_level_met_district_grade_bm_pm_period_total_students_enrolled
    ) as measure_level_met_district_grade_bm_pm_period_percent_met,
    safe_divide(
        measure_level_met_district_bm_pm_period_total_students_assessed,
        measure_level_met_district_bm_pm_period_total_students_enrolled
    ) as measure_level_met_district_bm_pm_period_percent,
from with_counts*/
{% set periods = ["Boy", "Boy->moy", "moy", "moy->eoy", "eoy"] %}

with
    student as (
        select
            e._dbt_source_relation,
            cast(e.academic_year as string) as enrollment_academic_year,
            'Kipp nJ/miami' as enrollment_district,
            e.region as enrollment_region,
            e.school_level as enrollment_school_level,
            e.schoolid as enrollment_school_id,
            e.school_name as enrollment_school,
            e.school_abbreviation as enrollment_school_abbreviation,
            e.studentid as student_id_enrollment,
            e.student_number as student_number_enrollment,
            e.lastfirst as student_name,
            e.first_name as student_first_name,
            e.last_name as student_last_name,
            case
                when cast(e.grade_level as string) = '0'
                then 'K'
                else cast(e.grade_level as string)
            end as enrollment_grade_level,
            case when is_out_of_district = true then 1 else 0 end as ood,
            e.gender as gender,
            e.ethnicity as ethnicity,
            case when e.is_homeless = true then 1 else 0 end as homeless,
            case when e.is_504 = true then 1 else 0 end as is_504,
            case when e.spedlep in ('no iEp', null) then 0 else 1 end as sped,
            case when e.lep_status = true then 1 else 0 end as lep,
            lunch_application_status as lunch_status
        from {{ ref("base_powerschool__student_enrollments") }} as e
        where
            academic_year = 2022
            and enroll_status = 0
            and rn_year = 1
            and grade_level <= 4
    ),

    schedule as (
        select
            c._dbt_source_relation,
            cast(c.cc_academic_year as string) as schedule_academic_year,
            'Kipp nJ/miami' as schedule_district,
            e.region as schedule_region,
            e.schedule_school_abbreviation,
            c.cc_schoolid as schedule_school_id,
            e.school_name as schedule_school,
            c.cc_studentid as student_id_schedule,
            e.student_number_enrollment as student_number_schedule,  -- needed to keep track of students who test at a grade level different from the class they are enrolled at
            case
                when c.courses_course_name in ('ela grK', 'ela K')
                then 'K'
                when c.courses_course_name = 'ela gr1'
                then '1'
                when c.courses_course_name = 'ela gr2'
                then '2'
                when c.courses_course_name = 'ela gr3'
                then '3'
                when c.courses_course_name = 'ela gr4'
                then '4'
            end as schedule_student_grade_level,
            c.cc_teacherid as teacher_id,
            c.teacher_lastfirst as teacher_number,
            c.teacher_lastfirst as teacher_name,
            c.courses_course_name as course_name,
            c.cc_course_number as course_number,
            c.cc_section_number as section_number,
            period as expected_test
        from {{ ref("base_powerschool__course_enrollments") }} as c
        left join  -- this join is needed to bring over the student_number onto the scheduling table, as mclass data contains only the student number field
            (
                select
                    e._dbt_source_relation,
                    cast(e.academic_year as string) as academic_year,
                    e.region,
                    e.schoolid as school_id,
                    e.school_abbreviation as schedule_school_abbreviation,
                    e.school_name,
                    e.studentid as student_id,
                    e.student_number as student_number_enrollment,
                    e.enroll_status
                from {{ ref("base_powerschool__student_enrollments") }} as e
                where
                    academic_year = 2022
                    and enroll_status = 0
                    and rn_year = 1
                    and grade_level <= 4
            ) as e
            on cast(c.cc_academic_year as string) = e.academic_year
            and c.cc_studentid = e.student_id
            and {{ union_dataset_join_clause(left_alias="c", right_alias="e") }}
        cross join unnest({{ periods }}) as period
        where
            c.cc_academic_year = 2022
            and not c.is_dropped_course
            and not c.is_dropped_section
            and c.rn_course_number_year = 1
            and c.courses_course_name
            in ('ELA grK', 'ELA K', 'ELA gr1', 'ELA gr2', 'ELA gr3', 'ELA gr4')
            and e.enroll_status = 0
    ),

    assessments_scores as (
        select
            left(bss.school_year, 4) as mclass_academic_year,  -- needed to extract the academic year format that matches nJ's syntax
            bss.primary_school_id as mclass_primary_school_id,
            bss.district_name as mclass_district_name,
            bss.school_name as mclass_school_name,
            bss.student_primary_id as mclass_student_number,
            bss.student_last_name as mclass_student_last_name,
            bss.student_first_name as mclass_student_first_name,
            bss.enrollment_grade as mclass_enrollment_grade,
            bss.reporting_class_name as mclass_reporting_class_name,
            bss.reporting_class_id as mclass_reporting_class_id,
            bss.official_teacher_name as mclass_official_teacher_name,
            bss.official_teacher_staff_id as mclass_official_teacher_staff_id,
            bss.assessing_teacher_name as mclass_assessing_teacher_name,
            bss.assessing_teacher_staff_id as mclass_assessing_teacher_staff_id,
            'benchmark' as assessment_type,
            bss.assessment as mclass_assessment,
            bss.assessment_edition as mclass_assessment_edition,
            bss.assessment_grade as mclass_assessment_grade,
            bss.benchmark_period as mclass_period,
            bss.client_date as mclass_client_date,
            bss.sync_date as mclass_sync_date,
            u.measure as mclass_measure,
            u.score as mclass_measure_score,
            u.level as mclass_measure_level,
            u.national_norm_percentile as measure_percentile,
            u.semester_growth as measure_semester_growth,
            u.year_growth as measure_year_growth,
            null as mclass_probe_number,
            null as mclass_total_number_of_probes,
            null as mclass_score_change

        from {{ ref("stg_amplify__benchmark_student_summary") }} as bss
        inner join
            {{ ref("int_amplify__benchmark_student_summary_unpivot") }} as u
            on bss.surrogate_key = u.surrogate_key

        union all

        select
            left(school_year, 4) as mclass_academic_year,  -- needed to extract the academic year format that matches nJ's syntax
            primary_school_id as mclass_primary_school_id,
            district_name as mclass_district_name,
            school_name as mclass_school_name,
            student_primary_id as mclass_student_number,
            student_last_name as mclass_student_last_name,
            student_first_name as mclass_student_first_name,
            cast(enrollment_grade as string) as mclass_enrollment_grade,
            reporting_class_name as mclass_reporting_class_name,
            reporting_class_id as mclass_reporting_class_id,
            official_teacher_name as mclass_official_teacher_name,
            official_teacher_staff_id as mclass_official_teacher_staff_id,
            assessing_teacher_name as mclass_assessing_teacher_name,
            cast(
                assessing_teacher_staff_id as string
            ) as mclass_assessing_teacher_staff_id,
            'pm' as assessment_type,
            assessment as mclass_assessment,
            assessment_edition as mclass_assessment_edition,
            cast(assessment_grade as string) as mclass_assessment_grade,
            pm_period as mclass_period,
            client_date as mclass_client_date,
            sync_date as mclass_sync_date,
            measure as mclass_measure,
            score as mclass_measure_score,
            null as mclass_measure_level,
            null as measure_percentile,
            null as measure_semester_growth,
            null as measure_year_growth,
            probe_number as mclass_probe_number,
            total_number_of_probes as mclass_total_number_of_probes,
            score_change as mclass_score_change
        from {{ ref("stg_amplify__pm_student_summary") }}
    )

select
    b.enrollment_academic_year,
    b.schedule_academic_year,
    b.enrollment_district,
    b.schedule_district,
    b.enrollment_region,
    b.schedule_region,
    b.enrollment_school_level,
    b.enrollment_school_id,
    b.schedule_school_id,
    b.enrollment_school,
    b.schedule_school,
    b.enrollment_school_abbreviation,
    b.schedule_school_abbreviation,
    b.student_number_enrollment,
    b.student_number_schedule,
    b.student_name,
    b.student_last_name,
    b.student_first_name,
    b.enrollment_grade_level,
    b.schedule_student_grade_level,
    b.ood,
    b.gender,
    b.ethnicity,
    b.homeless,
    b.is_504,
    b.sped,
    b.lep,
    b.lunch_status,
    b.enrolled_but_not_scheduled,
    b.student_has_assessment_data,
    b.teacher_id,
    b.teacher_name,
    b.course_name,
    b.course_number,
    b.section_number,
    b.expected_test,
    b.mclass_district_name,
    b.mclass_school_name,
    b.mclass_student_number,
    b.mclass_student_number_bm,
    b.mclass_student_number_pm,
    b.mclass_student_last_name,
    b.mclass_student_first_name,
    b.mclass_enrollment_grade,
    b.mclass_reporting_class_name,
    b.mclass_reporting_class_id,
    b.mclass_official_teacher_name,
    b.mclass_official_teacher_staff_id,
    b.mclass_assessing_teacher_name,
    b.mclass_assessing_teacher_staff_id,
    b.mclass_assessment,
    b.mclass_assessment_edition,
    b.mclass_assessment_grade,
    b.mclass_period,
    b.mclass_client_date,
    b.mclass_sync_date,
    b.mclass_probe_number,
    b.mclass_total_number_of_probes,
    b.mclass_measure,
    b.mclass_measure_score,
    b.mclass_score_change,
    b.mclass_measure_level,
    b.measure_percentile,
    b.measure_semester_growth,
    b.measure_year_growth,
    -- participation rates by school_course_section
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.section_number,
            b.expected_test
    ) as participation_school_course_section_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.section_number,
            b.expected_test
    ) as participation_school_course_section_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_school_id,
                b.course_name,
                b.section_number,
                b.expected_test
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.section_number,
                            b.expected_test
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.section_number,
                            b.expected_test
                    )
            end
        ),
        4
    ) as participation_school_course_section_bm_pm_period_percent,
    -- participation rates by school_course
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.expected_test
    ) as participation_school_course_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.expected_test
    ) as participation_school_course_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_school_id,
                b.course_name,
                b.expected_test
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.expected_test
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.expected_test
                    )
            end
        ),
        4
    ) as participation_school_course_bm_pm_period_percent,
    -- participation rates by school_grade
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.schedule_student_grade_level,
            b.expected_test
    ) as participation_school_grade_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.schedule_student_grade_level,
            b.expected_test
    ) as participation_school_grade_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_school_id,
                b.schedule_student_grade_level,
                b.expected_test
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.schedule_student_grade_level,
                            b.expected_test
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.schedule_student_grade_level,
                            b.expected_test
                    )
            end
        ),
        4
    ) as participation_school_grade_bm_pm_period_percent,
    -- participation rates by school
    count(distinct b.mclass_student_number) over (
        partition by b.schedule_academic_year, b.schedule_school_id, b.expected_test
    ) as participation_school_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by b.schedule_academic_year, b.schedule_school_id, b.expected_test
    ) as participation_school_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by b.schedule_academic_year, b.schedule_school_id, b.expected_test
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.expected_test
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.expected_test
                    )
            end
        ),
        4
    ) as participation_school_bm_pm_period_percent,
    -- participation rates by region_grade
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_region,
            b.schedule_student_grade_level,
            b.expected_test
    ) as participation_region_grade_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_region,
            b.schedule_student_grade_level,
            b.expected_test
    ) as participation_region_grade_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_region,
                b.schedule_student_grade_level,
                b.expected_test
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_region,
                            b.schedule_student_grade_level,
                            b.expected_test
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_region,
                            b.schedule_student_grade_level,
                            b.expected_test
                    )
            end
        ),
        4
    ) as participation_region_grade_bm_pm_period_percent,
    -- participation rates by region
    count(distinct b.mclass_student_number) over (
        partition by b.schedule_academic_year, b.schedule_region, b.expected_test
    ) as participation_region_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by b.schedule_academic_year, b.schedule_region, b.expected_test
    ) as participation_region_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by b.schedule_academic_year, b.schedule_region, b.expected_test
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year, b.schedule_region, b.expected_test
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year, b.schedule_region, b.expected_test
                    )
            end
        ),
        4
    ) as participation_region_bm_pm_period_percent,
    -- participation rates by district_grade
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_district,
            b.schedule_student_grade_level,
            b.expected_test
    ) as participation_district_grade_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_district,
            b.schedule_student_grade_level,
            b.expected_test
    ) as participation_district_grade_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_district,
                b.schedule_student_grade_level,
                b.expected_test
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.schedule_student_grade_level,
                            b.expected_test
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.schedule_student_grade_level,
                            b.expected_test
                    )
            end
        ),
        4
    ) as participation_district_grade_bm_pm_period_percent,
    -- participation rates by district
    count(distinct b.mclass_student_number) over (
        partition by b.schedule_academic_year, b.schedule_district, b.expected_test
    ) as participation_district_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by b.schedule_academic_year, b.schedule_district, b.expected_test
    ) as participation_district_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by b.schedule_academic_year, b.schedule_district, b.expected_test
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.expected_test
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.expected_test
                    )
            end
        ),
        4
    ) as participation_district_bm_pm_period_percent,
    -- measure score met rates by school_course_section
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.section_number,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_score
    ) as measure_score_met_school_course_section_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.section_number,
            b.expected_test,
            b.mclass_measure
    ) as measure_score_met_school_course_section_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_school_id,
                b.course_name,
                b.section_number,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_score
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.section_number,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.section_number,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_score_met_school_course_section_bm_pm_period_percent,
    -- measure score met rates by school_course
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_score
    ) as measure_score_met_school_course_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.expected_test,
            b.mclass_measure
    ) as measure_score_met_school_course_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_school_id,
                b.course_name,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_score
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_score_met_school_course_bm_pm_period_percent,
    -- measure score met rates by school_grade
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_score
    ) as measure_score_met_school_grade_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure
    ) as measure_score_met_school_grade_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_school_id,
                b.schedule_student_grade_level,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_score
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_score_met_school_grade_bm_pm_period_percent,
    -- measure score met rates by school
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_score
    ) as measure_score_met_school_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.expected_test,
            b.mclass_measure
    ) as measure_score_met_school_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_school_id,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_score
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_score_met_school_bm_pm_period_percent,
    -- measure score met rates by region_grade
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_region,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_score
    ) as measure_score_met_region_grade_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_region,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure
    ) as measure_score_met_region_grade_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_region,
                b.schedule_student_grade_level,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_score
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_region,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_region,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_score_met_region_grade_bm_pm_period_percent,
    -- measure score met rates by region
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_region,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_score
    ) as measure_score_met_region_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_region,
            b.expected_test,
            b.mclass_measure
    ) as measure_score_met_region_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_region,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_score
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_region,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_region,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_score_met_region_bm_pm_period_percent,
    -- measure score met rates by district_grade
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_district,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_score
    ) as measure_score_met_district_grade_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_district,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure
    ) as measure_score_met_district_grade_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_district,
                b.schedule_student_grade_level,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_score
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_score_met_district_grade_bm_pm_period_percent_met,
    -- measure score met rates by district
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_district,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_score
    ) as measure_score_met_district_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_district,
            b.expected_test,
            b.mclass_measure
    ) as measure_score_met_district_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_district,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_score
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_score_met_district_bm_pm_period_percent,
    -- measure level met rates by school_course_section
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.section_number,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_level
    ) as measure_level_met_school_course_section_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.section_number,
            b.expected_test,
            b.mclass_measure
    ) as measure_level_met_school_course_section_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_school_id,
                b.course_name,
                b.section_number,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_level
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.section_number,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.section_number,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_level_met_school_course_section_bm_pm_period_percent,
    -- measure level met rates by school_course
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_level
    ) as measure_level_met_school_course_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.course_name,
            b.expected_test,
            b.mclass_measure
    ) as measure_level_met_school_course_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_school_id,
                b.course_name,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_level
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.course_name,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_level_met_school_course_bm_pm_period_percent,
    -- measure level met rates by school_grade
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_level
    ) as measure_level_met_school_grade_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure
    ) as measure_level_met_school_grade_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_school_id,
                b.schedule_student_grade_level,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_level
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_level_met_school_grade_bm_pm_period_percent,
    -- measure level met rates by school
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_level
    ) as measure_level_met_school_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_school_id,
            b.expected_test,
            b.mclass_measure
    ) as measure_level_met_school_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_school_id,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_level
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_school_id,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_level_met_school_bm_pm_period_percent,
    -- measure level met rates by region_grade
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_region,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_level
    ) as measure_level_met_region_grade_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_region,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure
    ) as measure_level_met_region_grade_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_region,
                b.schedule_student_grade_level,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_level
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_region,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_region,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_level_met_region_grade_bm_pm_period_percent,
    -- measure level met rates by region
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_region,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_level
    ) as measure_level_met_region_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_region,
            b.expected_test,
            b.mclass_measure
    ) as measure_level_met_region_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_region,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_level
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_region,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_region,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_level_met_region_bm_pm_period_percent,
    -- measure level met rates by district_grade
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_district,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_level
    ) as measure_level_met_district_grade_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_district,
            b.schedule_student_grade_level,
            b.expected_test,
            b.mclass_measure
    ) as measure_level_met_district_grade_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_district,
                b.schedule_student_grade_level,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_level
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.schedule_student_grade_level,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_level_met_district_grade_bm_pm_period_percent,
    -- measure level met rates by district
    count(distinct b.mclass_student_number) over (
        partition by
            b.schedule_academic_year,
            b.schedule_district,
            b.expected_test,
            b.mclass_measure,
            b.mclass_measure_level
    ) as measure_level_met_district_bm_pm_period_total_students_assessed,
    count(distinct b.student_number_schedule) over (
        partition by
            b.schedule_academic_year,
            b.schedule_district,
            b.expected_test,
            b.mclass_measure
    ) as measure_level_met_district_bm_pm_period_total_students_scheduled,
    round(
        count(distinct b.mclass_student_number) over (
            partition by
                b.schedule_academic_year,
                b.schedule_district,
                b.expected_test,
                b.mclass_measure,
                b.mclass_measure_level
        ) / (
            case
                when
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.expected_test,
                            b.mclass_measure
                    )
                    = 0
                then null
                else
                    count(distinct b.student_number_schedule) over (
                        partition by
                            b.schedule_academic_year,
                            b.schedule_district,
                            b.expected_test,
                            b.mclass_measure
                    )
            end
        ),
        4
    ) as measure_level_met_district_bm_pm_period_percent

from
    (
        select
            s.enrollment_academic_year,
            m.schedule_academic_year,
            s.enrollment_district,
            m.schedule_district,
            s.enrollment_region,
            m.schedule_region,
            s.enrollment_school_level,
            s.enrollment_school_id,
            m.schedule_school_id,
            s.enrollment_school,
            m.schedule_school,
            s.enrollment_school_abbreviation,
            m.schedule_school_abbreviation,
            s.student_number_enrollment,
            m.student_number_schedule,
            s.student_name,
            s.student_last_name,
            s.student_first_name,
            s.enrollment_grade_level,
            m.schedule_student_grade_level,
            s.ood,
            s.gender,
            s.ethnicity,
            s.homeless,
            s.is_504,
            s.sped,
            s.lep,
            s.lunch_status,
            m.teacher_id,
            m.teacher_name,
            m.course_name,
            m.course_number,
            m.section_number,
            m.expected_test,
            case
                when m.student_number_schedule is null then 0 else 1
            end as enrolled_but_not_scheduled,  -- tagging students as enrolled in school but not scheduled for the course that would allow them to take the diBels test
            case
                when
                    m.student_number_schedule is not null
                    and d.mclass_student_number is null
                then 0
                else 1
            end as student_has_assessment_data,  -- tagging students who are schedule for the correct class but have not tested yet for the expected assessment term
            d.mclass_district_name,
            d.mclass_school_name,
            d.mclass_student_number,
            case
                when d.mclass_period in ('BOY', 'MOY', 'EOY')
                then d.mclass_student_number
                else null
            end as mclass_student_number_bm,  -- another tag for students who tested for benchmarks
            case
                when d.mclass_period in ('BOY->MOY', 'MOY->EOY')
                then d.mclass_student_number
                else null
            end as mclass_student_number_pm,  -- another tag for students who tested for progress monitoring
            d.mclass_student_last_name,
            d.mclass_student_first_name,
            d.mclass_enrollment_grade,
            d.mclass_reporting_class_name,
            d.mclass_reporting_class_id,
            d.mclass_official_teacher_name,
            d.mclass_official_teacher_staff_id,
            d.mclass_assessing_teacher_name,
            d.mclass_assessing_teacher_staff_id,
            d.mclass_assessment,
            d.mclass_assessment_edition,
            d.mclass_assessment_grade,
            d.mclass_period,
            d.mclass_client_date,
            d.mclass_sync_date,
            d.mclass_probe_number,
            d.mclass_total_number_of_probes,
            d.mclass_measure,
            cast(d.mclass_measure_score as string) as mclass_measure_score,
            d.mclass_score_change,
            d.mclass_measure_level,
            d.measure_percentile,
            d.measure_semester_growth,
            d.measure_year_growth
        from student as s
        left join
            schedule as m
            on s.enrollment_academic_year = m.schedule_academic_year
            and s.student_number_enrollment = m.student_number_schedule
        left join
            assessments_scores as d
            on m.schedule_academic_year = d.mclass_academic_year
            and m.student_number_schedule = d.mclass_student_number
            and m.expected_test = d.mclass_period  -- this last join on field is to ensure rows are generated for all expected tests, even if the student did not assess for them
    ) as b
where b.enrollment_grade_level not in ('3', '4')  -- excluding 3rd and 4th graders until iready scores are available
