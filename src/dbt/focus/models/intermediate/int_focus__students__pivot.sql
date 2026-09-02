with
    encoded as (
        select
            student_id,
            cast(ethnicity_hispanic_or_latino as string) as custom_100000105,
            cast(race_white as string) as custom_100000104,
            cast(race_black_or_african_american as string) as custom_100000102,
            cast(race_asian as string) as custom_100000101,
            cast(sex as string) as custom_200000000,
            cast(race_american_indian_or_alaska_native as string) as custom_100000100,
            cast(
                race_native_hawaiian_or_other_pacific_islander as string
            ) as custom_100000103,
            cast(residence_county as string) as custom_837,
            cast(`language` as string) as custom_200000005,
            cast(primary_language_spoken_in_home as string) as custom_546,
            cast(free_reduced_meals_program as string) as custom_71,
            cast(native_language_student as string) as custom_65,
            cast(homeless_student_pk_12 as string) as custom_820,
            cast(homeless_unaccompanied_youth as string) as custom_818,
            cast(idea_educational_environment as string) as custom_863,
            cast(english_language_learner_pk_12 as string) as custom_626,
            cast(pe_waiver as string) as custom_942,
            cast(graduation_option as string) as custom_760,
            cast(doe_test_accommodations_access_for_ells as string) as custom_829,
            cast(ese_fefp_code as string) as custom_698,
            cast(gifted_eligibility as string) as custom_999,
            cast(prekindergarten_program_participation as string) as custom_640,
            cast(country_of_birth as string) as custom_728,
            cast(year_entered_ninth_grade as string) as custom_1429,
            cast(florida_first_start_program_participant as string) as custom_1087,
            cast(
                even_start_family_literacy_program_participant as string
            ) as custom_1086,
            cast(multi_birth_for_faster as string) as custom_1050,
            cast(resident_status as string) as custom_128,
            cast(screening_for_hearing_grade_kg as string) as custom_132,
            cast(screening_for_vision_problems as string) as custom_134,
            cast(birth_date_verification as string) as custom_200000207,
            cast(aice_diploma as string) as custom_200000255,
            cast(
                diploma_florida_seal_of_fine_arts_designation as string
            ) as custom_200000297,
            cast(residency_for_tuition_purposes as string) as custom_2012197244,
            cast(
                bright_futures_volunteer_service_requirement_met as string
            ) as custom_202,
            cast(national_merit_scholar as string) as custom_216,
            cast(national_achievement_scholar as string) as custom_217,
            cast(national_hispanic_scholar as string) as custom_245,
            cast(aice_program_participant as string) as custom_264,
            cast(ib_diploma as string) as custom_266,
            cast(college_ready_diploma as string) as custom_267,
            cast(differentiated_diploma as string) as custom_268,
            cast(additional_school_year as string) as custom_699,
            cast(migrant_status_term as string) as custom_789,
            cast(basis_of_entry as string) as custom_660,
            cast(first_basis_of_exit as string) as custom_661,
            cast(single_ethnicity as string) as custom_200000001,
        from {{ ref("stg_focus__students") }}
    ),

    unpivoted as (
        select student_id, column_name, stored_value,
        from
            encoded unpivot (
                stored_value for column_name in (
                    custom_100000105,
                    custom_100000104,
                    custom_100000102,
                    custom_100000101,
                    custom_200000000,
                    custom_100000100,
                    custom_100000103,
                    custom_837,
                    custom_200000005,
                    custom_546,
                    custom_71,
                    custom_65,
                    custom_820,
                    custom_818,
                    custom_863,
                    custom_626,
                    custom_942,
                    custom_760,
                    custom_829,
                    custom_698,
                    custom_999,
                    custom_640,
                    custom_728,
                    custom_1429,
                    custom_1087,
                    custom_1086,
                    custom_1050,
                    custom_128,
                    custom_132,
                    custom_134,
                    custom_200000207,
                    custom_200000255,
                    custom_200000297,
                    custom_2012197244,
                    custom_202,
                    custom_216,
                    custom_217,
                    custom_245,
                    custom_264,
                    custom_266,
                    custom_267,
                    custom_268,
                    custom_699,
                    custom_789,
                    custom_660,
                    custom_661,
                    custom_200000001
                )
            )
    ),

    decoded as (
        select
            unpivoted.student_id,
            unpivoted.column_name,
            unpivoted.stored_value,

            opt.code,
            opt.label,
        from unpivoted
        left join
            {{ ref("int_focus__custom_field_options") }} as opt
            on unpivoted.column_name = opt.column_name
            and unpivoted.stored_value in (opt.option_id, opt.code)
            and opt.source_class = 'SISStudent'
    )

select *,
from
    decoded pivot (
        any_value(stored_value) as `value`,
        any_value(code) as code,
        any_value(label) as label
        for column_name in (
            'custom_100000105' as ethnicity_hispanic_or_latino,
            'custom_100000104' as race_white,
            'custom_100000102' as race_black_or_african_american,
            'custom_100000101' as race_asian,
            'custom_200000000' as sex,
            'custom_100000100' as race_american_indian_or_alaska_native,
            'custom_100000103' as race_native_hawaiian_or_other_pacific_islander,
            'custom_837' as residence_county,
            'custom_200000005' as `language`,
            'custom_546' as primary_language_spoken_in_home,
            'custom_71' as free_reduced_meals_program,
            'custom_65' as native_language_student,
            'custom_820' as homeless_student_pk_12,
            'custom_818' as homeless_unaccompanied_youth,
            'custom_863' as idea_educational_environment,
            'custom_626' as english_language_learner_pk_12,
            'custom_942' as pe_waiver,
            'custom_760' as graduation_option,
            'custom_829' as doe_test_accommodations_access_for_ells,
            'custom_698' as ese_fefp_code,
            'custom_999' as gifted_eligibility,
            'custom_640' as prekindergarten_program_participation,
            'custom_728' as country_of_birth,
            'custom_1429' as year_entered_ninth_grade,
            'custom_1087' as florida_first_start_program_participant,
            'custom_1086' as even_start_family_literacy_program_participant,
            'custom_1050' as multi_birth_for_faster,
            'custom_128' as resident_status,
            'custom_132' as screening_for_hearing_grade_kg,
            'custom_134' as screening_for_vision_problems,
            'custom_200000207' as birth_date_verification,
            'custom_200000255' as aice_diploma,
            'custom_200000297' as diploma_florida_seal_of_fine_arts_designation,
            'custom_2012197244' as residency_for_tuition_purposes,
            'custom_202' as bright_futures_volunteer_service_requirement_met,
            'custom_216' as national_merit_scholar,
            'custom_217' as national_achievement_scholar,
            'custom_245' as national_hispanic_scholar,
            'custom_264' as aice_program_participant,
            'custom_266' as ib_diploma,
            'custom_267' as college_ready_diploma,
            'custom_268' as differentiated_diploma,
            'custom_699' as additional_school_year,
            'custom_789' as migrant_status_term,
            'custom_660' as basis_of_entry,
            'custom_661' as first_basis_of_exit,
            'custom_200000001' as single_ethnicity
        )
    )
