with
    ap_courses as (
        select
            cast(e.grade_level as string) as grade_level,

            case
                x.ap_course_name
                when 'AP US History'
                then 'AP United States History'
                when 'AP US Government and Politics'
                then 'AP United States Government and Politics'
                when 'AP Pre-Calculus'
                then 'AP Precalculus'
                when 'AP Studio Art: 2-D Design Portfolio'
                then 'AP 2-D Art and Design'
                when 'AP Studio Art: 3-D Design Portfolio'
                then 'AP 3-D Art and Design'
                when 'AP Studio Art: Drawing Portfolio'
                then 'AP Drawing'
                else x.ap_course_name
            end as ap_course_name,

            if(
                e.school_name = 'KIPP Cooper Norcross High',
                'KIPP Cooper Norcross High School',
                e.school_name
            ) as school_name,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.academic_year = s.cc_academic_year
            and e.studentid = s.cc_studentid
            and e._dbt_source_project = s._dbt_source_project
            and s.rn_course_number_year = 1
            and s.is_ap_course
            and not s.is_dropped_section
        inner join
            {{ ref("stg_google_sheets__collegeboard__ap_course_crosswalk") }} as x
            on s.ap_course_subject = x.ps_ap_course_subject_code
        where
            e.academic_year = {{ var("current_academic_year") - 1 }}
            and e.school_level = 'HS'
            and e.rn_year = 1
            and e.is_enrolled_recent
    ),

    grade_levels as (
        select
            school_name,
            ap_course_name,

            string_agg(distinct grade_level order by grade_level) as grade_levels_list,

        from ap_courses
        group by school_name, ap_course_name
    )

select
    school_name,

    ap_2d_art_and_design,
    ap_3d_art_and_design,
    ap_art_history,
    ap_biology,
    ap_calculus_ab,
    ap_calculus_bc,
    ap_calculus_bc_ab_subscore,
    ap_chemistry,
    ap_chinese_language_and_culture,
    ap_comparative_government_and_politics,
    ap_computer_science_a,
    ap_computer_science_principles,
    ap_drawing,
    ap_english_language_and_composition,
    ap_english_literature_and_composition,
    ap_environmental_science,
    ap_european_history,
    ap_french_language_and_culture,
    ap_german_language_and_culture,
    ap_human_geography,
    ap_italian_language_and_culture,
    ap_japanese_language_and_culture,
    ap_latin,
    ap_macroeconomics,
    ap_microeconomics,
    ap_music_aural_subscore,
    ap_music_non_aural_subscore,
    ap_music_theory,
    ap_physics_1,
    ap_physics_2,
    ap_physics_c_electricity_and_magnetism,
    ap_physics_c_mechanics,
    ap_psychology,
    ap_research,
    ap_seminar,
    ap_spanish_language_and_culture,
    ap_spanish_literature_and_culture,
    ap_statistics,
    ap_us_government_and_politics,
    ap_us_history,
    ap_world_history_modern,
    ap_african_american_studies,
    ap_pre_calculus,

from
    grade_levels pivot (
        max(grade_levels_list) for ap_course_name in (
            -- placeholder columns (no crosswalk/course data maps to these --
            -- see the model description) always pivot to NULL, matching a
            -- school that simply doesn't offer the course
            'AP 2-D Art and Design' as ap_2d_art_and_design,
            'AP 3-D Art and Design' as ap_3d_art_and_design,
            'AP Art History' as ap_art_history,
            'AP Biology' as ap_biology,
            'AP Calculus AB' as ap_calculus_ab,
            'AP Calculus BC' as ap_calculus_bc,
            'AP Calculus BC: AB Subscore' as ap_calculus_bc_ab_subscore,
            'AP Chemistry' as ap_chemistry,
            'AP Chinese Language and Culture' as ap_chinese_language_and_culture,
            'AP Comparative Government and Politics'
            as ap_comparative_government_and_politics,
            'AP Computer Science A' as ap_computer_science_a,
            'AP Computer Science Principles' as ap_computer_science_principles,
            'AP Drawing' as ap_drawing,
            'AP English Language and Composition'
            as ap_english_language_and_composition,
            'AP English Literature and Composition'
            as ap_english_literature_and_composition,
            'AP Environmental Science' as ap_environmental_science,
            'AP European History' as ap_european_history,
            'AP French Language and Culture' as ap_french_language_and_culture,
            'AP German Language and Culture' as ap_german_language_and_culture,
            'AP Human Geography' as ap_human_geography,
            'AP Italian Language and Culture' as ap_italian_language_and_culture,
            'AP Japanese Language and Culture' as ap_japanese_language_and_culture,
            'AP Latin' as ap_latin,
            'AP Macroeconomics' as ap_macroeconomics,
            'AP Microeconomics' as ap_microeconomics,
            'AP Music Aural Subscore' as ap_music_aural_subscore,
            'AP Music Non-Aural Subscore' as ap_music_non_aural_subscore,
            'AP Music Theory' as ap_music_theory,
            'AP Physics 1' as ap_physics_1,
            'AP Physics 2' as ap_physics_2,
            'AP Physics C: Electricity and Magnetism'
            as ap_physics_c_electricity_and_magnetism,
            'AP Physics C: Mechanics' as ap_physics_c_mechanics,
            'AP Psychology' as ap_psychology,
            'AP Research' as ap_research,
            'AP Seminar' as ap_seminar,
            'AP Spanish Language and Culture' as ap_spanish_language_and_culture,
            'AP Spanish Literature and Culture' as ap_spanish_literature_and_culture,
            'AP Statistics' as ap_statistics,
            'AP United States Government and Politics' as ap_us_government_and_politics,
            'AP United States History' as ap_us_history,
            'AP World History: Modern' as ap_world_history_modern,
            'AP African American Studies' as ap_african_american_studies,
            'AP Precalculus' as ap_pre_calculus
        )
    )
