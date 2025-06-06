with
    -- trunk-ignore(sqlfluff/ST03)
    ap as (
        select a.*, x.powerschool_student_number,
        from {{ source("collegeboard", "src_collegeboard__ap") }} as a
        left join
            {{ ref("stg_collegeboard__ap_id_crosswalk") }} as x
            on a.ap_number_ap_id = x.college_board_id
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="ap",
                partition_by="powerschool_student_number",
                order_by="_dagster_partition_school_year desc",
            )
        }}
    )

select
    _dagster_partition_school_year as enrollment_school_year,
    ap_number_ap_id,
    powerschool_student_number,
    student_identifier,
    first_name,
    middle_initial,
    last_name,
    gender,
    ai_code,
    ai_institution_name,

    admin_year_01,
    admin_year_02,
    admin_year_03,
    admin_year_04,
    admin_year_05,
    admin_year_06,
    admin_year_07,
    admin_year_08,
    admin_year_09,
    admin_year_10,
    admin_year_11,
    admin_year_12,
    admin_year_13,
    admin_year_14,
    admin_year_15,
    admin_year_16,
    admin_year_17,
    admin_year_18,
    admin_year_19,
    admin_year_20,
    admin_year_21,
    admin_year_22,
    admin_year_23,
    admin_year_24,
    admin_year_25,
    admin_year_26,
    admin_year_27,
    admin_year_28,
    admin_year_29,
    admin_year_30,
    exam_code_01,
    exam_code_02,
    exam_code_03,
    exam_code_04,
    exam_code_05,
    exam_code_06,
    exam_code_07,
    exam_code_08,
    exam_code_09,
    exam_code_10,
    exam_code_11,
    exam_code_12,
    exam_code_13,
    exam_code_14,
    exam_code_15,
    exam_code_16,
    exam_code_17,
    exam_code_18,
    exam_code_19,
    exam_code_20,
    exam_code_21,
    exam_code_22,
    exam_code_23,
    exam_code_24,
    exam_code_25,
    exam_code_26,
    exam_code_27,
    exam_code_28,
    exam_code_29,
    exam_code_30,
    exam_grade_01,
    exam_grade_02,
    exam_grade_03,
    exam_grade_04,
    exam_grade_05,
    exam_grade_06,
    exam_grade_07,
    exam_grade_08,
    exam_grade_09,
    exam_grade_10,
    exam_grade_11,
    exam_grade_12,
    exam_grade_13,
    exam_grade_14,
    exam_grade_15,
    exam_grade_16,
    exam_grade_17,
    exam_grade_18,
    exam_grade_19,
    exam_grade_20,
    exam_grade_21,
    exam_grade_22,
    exam_grade_23,
    exam_grade_24,
    exam_grade_25,
    exam_grade_26,
    exam_grade_27,
    exam_grade_28,
    exam_grade_29,
    exam_grade_30,
    irregularity_code_1_01,
    irregularity_code_1_02,
    irregularity_code_1_03,
    irregularity_code_1_04,
    irregularity_code_1_05,
    irregularity_code_1_06,
    irregularity_code_1_07,
    irregularity_code_1_08,
    irregularity_code_1_09,
    irregularity_code_1_10,
    irregularity_code_1_11,
    irregularity_code_1_12,
    irregularity_code_1_13,
    irregularity_code_1_14,
    irregularity_code_1_15,
    irregularity_code_1_16,
    irregularity_code_1_17,
    irregularity_code_1_18,
    irregularity_code_1_19,
    irregularity_code_1_20,
    irregularity_code_1_21,
    irregularity_code_1_22,
    irregularity_code_1_23,
    irregularity_code_1_24,
    irregularity_code_1_25,
    irregularity_code_1_26,
    irregularity_code_1_27,
    irregularity_code_1_28,
    irregularity_code_1_29,
    irregularity_code_1_30,
    irregularity_code_2_01,
    irregularity_code_2_02,
    irregularity_code_2_03,
    irregularity_code_2_04,
    irregularity_code_2_05,
    irregularity_code_2_06,
    irregularity_code_2_07,
    irregularity_code_2_08,
    irregularity_code_2_09,
    irregularity_code_2_10,
    irregularity_code_2_11,
    irregularity_code_2_12,
    irregularity_code_2_13,
    irregularity_code_2_14,
    irregularity_code_2_15,
    irregularity_code_2_16,
    irregularity_code_2_17,
    irregularity_code_2_18,
    irregularity_code_2_19,
    irregularity_code_2_20,
    irregularity_code_2_21,
    irregularity_code_2_22,
    irregularity_code_2_23,
    irregularity_code_2_24,
    irregularity_code_2_25,
    irregularity_code_2_26,
    irregularity_code_2_27,
    irregularity_code_2_28,
    irregularity_code_2_29,
    irregularity_code_2_30,

    parse_date('%m%d%y', date_of_birth) as date_of_birth,

    case
        grade_level when '4' then 9 when '5' then 10 when '6' then 11 when '7' then 12
    end as grade_level,

{# unused columns #}
{# _dagster_partition_school, #}
{# ai_country_code, #}
{# ai_international_postal_code, #}
{# ai_province, #}
{# ai_state, #}
{# ai_street_address_1, #}
{# ai_street_address_2, #}
{# ai_street_address_3, #}
{# ai_zip_code, #}
{# award_type_1, #}
{# award_type_2, #}
{# award_type_3, #}
{# award_type_4, #}
{# award_type_5, #}
{# award_type_6, #}
{# award_year_1, #}
{# award_year_2, #}
{# award_year_3, #}
{# award_year_4, #}
{# award_year_5, #}
{# award_year_6, #}
{# best_language, #}
{# college_code, #}
{# contact_name, #}
{# date_grades_released_to_college, #}
{# date_of_last_student_update, #}
{# date_of_this_report, #}
{# derived_aggregate_race_ethnicity_2016_and_forward, #}
{# di_country_code, #}
{# di_institution_name, #}
{# di_international_postal_code, #}
{# di_province, #}
{# di_state, #}
{# di_street_address_1, #}
{# di_street_address_2, #}
{# di_street_address_3, #}
{# di_zip_code, #}
{# previous_ai_code_1, #}
{# previous_ai_code_2, #}
{# previous_ai_year_1, #}
{# previous_ai_year_2, #}
{# race_ethnicity_student_response_2016_and_forward, #}
{# student_country_code, #}
{# student_international_postal_code, #}
{# student_province, #}
{# student_state, #}
{# student_street_address_1, #}
{# student_street_address_2, #}
{# student_street_address_3, #}
{# student_zip_code, #}
{# always blank */ #}
{# ethnic_group_2015_and_prior, #}
{# school_id, #}
{# class_section_code_01, #}
{# class_section_code_02, #}
{# class_section_code_03, #}
{# class_section_code_04, #}
{# class_section_code_05, #}
{# class_section_code_06, #}
{# class_section_code_07, #}
{# class_section_code_08, #}
{# class_section_code_09, #}
{# class_section_code_10, #}
{# class_section_code_11, #}
{# class_section_code_12, #}
{# class_section_code_13, #}
{# class_section_code_14, #}
{# class_section_code_15, #}
{# class_section_code_16, #}
{# class_section_code_17, #}
{# class_section_code_18, #}
{# class_section_code_19, #}
{# class_section_code_20, #}
{# class_section_code_21, #}
{# class_section_code_22, #}
{# class_section_code_23, #}
{# class_section_code_24, #}
{# class_section_code_25, #}
{# class_section_code_26, #}
{# class_section_code_27, #}
{# class_section_code_28, #}
{# class_section_code_29, #}
{# class_section_code_30, #}
from deduplicate
