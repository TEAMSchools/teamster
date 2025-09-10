with
    ap_courses as (
        select
            x.ap_course_name,

            cast(e.grade_level as string) as grade_level,

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
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
            and s.rn_course_number_year = 1
            and s.is_ap_course
            and not s.is_dropped_section
        inner join
            {{ ref("stg_collegeboard__ap_course_crosswalk") }} as x
            on s.ap_course_subject = x.ps_ap_course_subject_code
        where
            e.academic_year = {{ var("current_academic_year") - 1 }}
            and e.school_level = 'HS'
            and e.rn_year = 1
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

    ap_african_american_studies,
    ap_art_history,
    ap_biology,
    ap_calculus_ab,
    ap_calculus_bc,
    ap_chemistry,
    ap_comparative_government_and_politics,
    ap_computer_science_a,
    ap_computer_science_principles,
    ap_english_language_and_composition,
    ap_english_literature_and_composition,
    ap_environmental_science,
    ap_french_language_and_culture,
    ap_human_geography,
    ap_macroeconomics,
    ap_microeconomics,
    ap_physics_1,
    ap_pre_calculus,
    ap_psychology,
    ap_seminar,
    ap_spanish_language_and_culture,
    ap_statistics,
    ap_2d_art_and_design_portfolio,
    ap_3d_art_and_design_portfolio,
    ap_drawing,
    ap_us_government_and_politics,
    ap_us_history,
    ap_world_history_modern,

from
    grade_levels pivot (
        max(grade_levels_list) for ap_course_name in (
            'AP African American Studies' as ap_african_american_studies,
            'AP Art History' as ap_art_history,
            'AP Biology' as ap_biology,
            'AP Calculus AB' as ap_calculus_ab,
            'AP Calculus BC' as ap_calculus_bc,
            'AP Chemistry' as ap_chemistry,
            'AP Comparative Government and Politics'
            as ap_comparative_government_and_politics,
            'AP Computer Science A' as ap_computer_science_a,
            'AP Computer Science Principles' as ap_computer_science_principles,
            'AP English Language and Composition'
            as ap_english_language_and_composition,
            'AP English Literature and Composition'
            as ap_english_literature_and_composition,
            'AP Environmental Science' as ap_environmental_science,
            'AP French Language and Culture' as ap_french_language_and_culture,
            'AP Human Geography' as ap_human_geography,
            'AP Macroeconomics' as ap_macroeconomics,
            'AP Microeconomics' as ap_microeconomics,
            'AP Physics 1' as ap_physics_1,
            'AP Pre-Calculus' as ap_pre_calculus,
            'AP Psychology' as ap_psychology,
            'AP Seminar' as ap_seminar,
            'AP Spanish Language and Culture' as ap_spanish_language_and_culture,
            'AP Statistics' as ap_statistics,
            'AP Studio Art: 2-D Design Portfolio' as ap_2d_art_and_design_portfolio,
            'AP Studio Art: 3-D Design Portfolio' as ap_3d_art_and_design_portfolio,
            'AP Studio Art: Drawing Portfolio' as ap_drawing,
            'AP US Government and Politics' as ap_us_government_and_politics,
            'AP US History' as ap_us_history,
            'AP World History: Modern' as ap_world_history_modern
        )
    )
