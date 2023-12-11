with
    ms_grad as (
        select _dbt_source_relation, student_number, ms_attended,
        from
            (
                select
                    _dbt_source_relation,
                    student_number,
                    school_abbreviation as ms_attended,
                    row_number() over (
                        partition by student_number order by exitdate desc
                    ) as rn,
                from {{ ref("base_powerschool__student_enrollments") }}
                where school_level = 'MS'
            ) as sub
        where rn = 1
    ),

    students_nj as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.region,
            e.schoolid,
            e.school_abbreviation as school,
            e.student_number,
            e.state_studentnumber,
            e.lastfirst as student_name,
            e.grade_level,
            e.enroll_status,
            e.is_out_of_district,
            e.gender,
            e.lunch_status as lunch_status,

            m.ms_attended,

            case
                when e.school_level in ('ES', 'MS')
                then advisory_name
                when school_level = 'HS'
                then e.advisor_lastfirst
            end as advisory,
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            ms_grad as m
            on e.student_number = m.student_number
            and {{ union_dataset_join_clause(left_alias="e", right_alias="m") }}
        where
            e.academic_year >= {{ var("current_academic_year") }} - 2
            and e.rn_year = 1
            and e.region in ('Camden', 'Newark')
            and e.grade_level > 2
            and e.schoolid != 999999
    ),

    students_fl as (
        select
            _dbt_source_relation,
            academic_year,
            region,
            schoolid,
            school_abbreviation as school,
            student_number,
            fleid,
            lastfirst as student_name,
            grade_level,
            enroll_status,
            is_out_of_district,
            gender,
            is_504,
            lep_status,
            lunch_status as lunch_status,
            case
                ethnicity when 'T' then 'T' when 'H' then 'H' else ethnicity
            end as race_ethnicity,
            case
                when spedlep like '%SPED%' then 'Has IEP' else 'No IEP'
            end as iep_status,
            case
                when school_level in ('ES', 'MS')
                then advisory_name
                when school_level = 'HS'
                then advisor_lastfirst
            end as advisory,
        from {{ ref("base_powerschool__student_enrollments") }}
        where
            academic_year >= {{ var("current_academic_year") }} - 2
            and rn_year = 1
            and region = 'Miami'
            and grade_level > 2
    ),

    schedules_current as (
        select
            _dbt_source_relation,
            cc_academic_year,
            students_student_number,
            courses_credittype,
            teacher_lastfirst as teacher_name,
            courses_course_name as course_name,
            cc_course_number as course_number,
            case
                courses_credittype
                when 'ENG'
                then 'ELA'
                when 'MATH'
                then 'Math'
                when 'SCI'
                then 'Science'
                when 'SOC'
                then 'Civics'
            end as discipline,
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            cc_academic_year = {{ var("current_academic_year") }}
            and rn_credittype_year = 1
            and not is_dropped_section
            and courses_credittype in ('ENG', 'MATH', 'SCI', 'SOC')
    ),

    schedules as (
        select
            e._dbt_source_relation,
            e.cc_academic_year,
            e.students_student_number,
            e.teacher_lastfirst as teacher_name,
            e.courses_course_name as course_name,
            e.cc_course_number as course_number,

            c.teacher_name as teacher_name_current,
            case
                e.courses_credittype
                when 'ENG'
                then 'ELA'
                when 'MATH'
                then 'Math'
                when 'SCI'
                then 'Science'
                when 'SOC'
                then 'Civics'
            end as discipline,
        from {{ ref("base_powerschool__course_enrollments") }} as e
        left join
            schedules_current as c
            on e.students_student_number = c.students_student_number
            and e.courses_credittype = c.courses_credittype
        where
            e.cc_academic_year >= {{ var("current_academic_year") }} - 2
            and e.rn_credittype_year = 1
            and not e.is_dropped_section
            and e.courses_credittype in ('ENG', 'MATH', 'SCI', 'SOC')
    ),

    assessments_nj as (
        select
            cast(academic_year as int) as academic_year,
            statestudentidentifier as state_id,
            assessment_name,
            subject_area as discipline,
            testcode as test_code,
            testscalescore as score,
            testperformancelevel as performance_band_level,
            is_proficient,
            case period when 'FallBlock' then 'Fall' else period end as admin,
            case period when 'FallBlock' then 'Fall' else period end as season,
            case
                when testcode in ('ELAGP', 'MATGP') and testperformancelevel = 2
                then 'Graduation Ready'
                when testcode in ('ELAGP', 'MATGP') and testperformancelevel = 1
                then 'Not Yet Graduation Ready'
                else testperformancelevel_text
            end as performance_band,
            case
                when twoormoreraces = 'Y'
                then 'T'
                when hispanicorlatinoethnicity = 'Y'
                then 'H'
                when americanindianoralaskanative = 'Y'
                then 'I'
                when asian = 'Y'
                then 'A'
                when blackorafricanamerican = 'Y'
                then 'B'
                when nativehawaiianorotherpacificislander = 'Y'
                then 'P'
                when white = 'Y'
                then 'W'
            end as race_ethnicity,
            case
                when studentwithdisabilities in ('IEP', 'B')
                then 'Has IEP'
                else 'No IEP'
            end as iep_status,
            case
                when studentwithdisabilities in ('504', 'B') then true else false
            end as is_504,
            case
                englishlearnerel
                when 'Y'
                then true
                when 'N'
                then false
                when null
                then null
            end as lep_status,
            case
                when assessmentgrade in ('Grade 10', 'Grade 11')
                then right(assessmentgrade, 2)
                when assessmentgrade is null
                then null
                else right(assessmentgrade, 1)
            end as test_grade,
            case
                when subject = 'English Language Arts/Literacy'
                then 'English Language Arts'
                else subject
            end as subject,
        from {{ ref("int_pearson__all_assessments") }}
        where cast(academic_year as int) >= {{ var("current_academic_year") }} - 2
    ),

    assessments_fl as (
        select
            cast(academic_year as int) as academic_year,
            student_id as state_id,
            'FAST' as assessment_name,
            cast(assessment_grade as string) as test_grade,
            administration_window as admin,
            scale_score as score,
            achievement_level as performance_band,
            achievement_level_int as performance_band_level,
            is_proficient,
            case
                administration_window
                when 'PM1'
                then 'Fall'
                when 'PM2'
                then 'Winter'
                when 'PM3'
                then 'Spring'
            end as season,
            case
                assessment_subject
                when 'ELAReading'
                then 'ELA'
                when 'Mathematics'
                then 'Math'
            end as discipline,
            case
                assessment_subject
                when 'ELAReading'
                then 'English Language Arts'
                when 'Mathematics'
                then 'Mathematics'
            end as subject,
            case
                when assessment_subject = 'ELAReading'
                then concat('ELA0', assessment_grade)
                else concat('MAT0', assessment_grade)
            end as test_code,
        from `teamster-332318.kipptaf_fldoe.stg_fldoe__fast`
        where achievement_level not in ('Insufficient to score', 'Invalidated')
        union all
        select
            cast(academic_year as int) as academic_year,
            fleid as state_id,
            'FSA' as assessment_name,
            cast(test_grade as string) as test_grade,
            'Spring' as admin,
            scale_score as score,
            achievement_level as performance_band,
            performance_level as performance_band_level,
            is_proficient,
            'Spring' as season,
            case
                test_subject
                when 'ELA'
                then 'ELA'
                when 'MATH'
                then 'Math'
                when 'SCIENCE'
                then 'Science'
            end as discipline,
            case
                test_subject
                when 'ELA'
                then 'English Language Arts'
                when 'MATH'
                then 'Mathematics'
                when 'SCIENCE'
                then 'Science'
            end as subject,
            case
                when test_subject = 'ELA'
                then concat('ELA0', test_grade)
                when test_subject = 'SCIENCE'
                then concat('SCI0', test_grade)
                else concat('MAT0', test_grade)
            end as test_code,
        from `teamster-332318.kippmiami_fldoe.stg_fldoe__fsa`
        where performance_level is not null
    ),
