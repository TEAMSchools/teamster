select
    ap_number_ap_id,

    /* unpivot cols */
    rn_exam_number,
    exam_code,
    irregularity_code_1,
    irregularity_code_2,

    x.powerschool_student_number,

    c1.description as exam_code_description,

    c2.description as irregularity_code_1_description,

    c3.description as irregularity_code_2_description,

    cast(exam_grade as int) as exam_grade,

    extract(year from parse_date('%y', admin_year)) as admin_year,

from
    {{ ref("stg_collegeboard__ap") }} unpivot (
        (
            admin_year,
            exam_code,
            exam_grade,
            irregularity_code_1,
            irregularity_code_2
        ) for rn_exam_number in (
            (
                admin_year_01,
                exam_code_01,
                exam_grade_01,
                irregularity_code_1_01,
                irregularity_code_2_01
            ) as 1,
            (
                admin_year_02,
                exam_code_02,
                exam_grade_02,
                irregularity_code_1_02,
                irregularity_code_2_02
            ) as 2,
            (
                admin_year_03,
                exam_code_03,
                exam_grade_03,
                irregularity_code_1_03,
                irregularity_code_2_03
            ) as 3,
            (
                admin_year_04,
                exam_code_04,
                exam_grade_04,
                irregularity_code_1_04,
                irregularity_code_2_04
            ) as 4,
            (
                admin_year_05,
                exam_code_05,
                exam_grade_05,
                irregularity_code_1_05,
                irregularity_code_2_05
            ) as 5,
            (
                admin_year_06,
                exam_code_06,
                exam_grade_06,
                irregularity_code_1_06,
                irregularity_code_2_06
            ) as 6,
            (
                admin_year_07,
                exam_code_07,
                exam_grade_07,
                irregularity_code_1_07,
                irregularity_code_2_07
            ) as 7,
            (
                admin_year_08,
                exam_code_08,
                exam_grade_08,
                irregularity_code_1_08,
                irregularity_code_2_08
            ) as 8,
            (
                admin_year_09,
                exam_code_09,
                exam_grade_09,
                irregularity_code_1_09,
                irregularity_code_2_09
            ) as 9,
            (
                admin_year_10,
                exam_code_10,
                exam_grade_10,
                irregularity_code_1_10,
                irregularity_code_2_10
            ) as 10,
            (
                admin_year_11,
                exam_code_11,
                exam_grade_11,
                irregularity_code_1_11,
                irregularity_code_2_11
            ) as 11,
            (
                admin_year_12,
                exam_code_12,
                exam_grade_12,
                irregularity_code_1_12,
                irregularity_code_2_12
            ) as 12,
            (
                admin_year_13,
                exam_code_13,
                exam_grade_13,
                irregularity_code_1_13,
                irregularity_code_2_13
            ) as 13,
            (
                admin_year_14,
                exam_code_14,
                exam_grade_14,
                irregularity_code_1_14,
                irregularity_code_2_14
            ) as 14,
            (
                admin_year_15,
                exam_code_15,
                exam_grade_15,
                irregularity_code_1_15,
                irregularity_code_2_15
            ) as 15,
            (
                admin_year_16,
                exam_code_16,
                exam_grade_16,
                irregularity_code_1_16,
                irregularity_code_2_16
            ) as 16,
            (
                admin_year_17,
                exam_code_17,
                exam_grade_17,
                irregularity_code_1_17,
                irregularity_code_2_17
            ) as 17,
            (
                admin_year_18,
                exam_code_18,
                exam_grade_18,
                irregularity_code_1_18,
                irregularity_code_2_18
            ) as 18,
            (
                admin_year_19,
                exam_code_19,
                exam_grade_19,
                irregularity_code_1_19,
                irregularity_code_2_19
            ) as 19,
            (
                admin_year_20,
                exam_code_20,
                exam_grade_20,
                irregularity_code_1_20,
                irregularity_code_2_20
            ) as 20,
            (
                admin_year_21,
                exam_code_21,
                exam_grade_21,
                irregularity_code_1_21,
                irregularity_code_2_21
            ) as 21,
            (
                admin_year_22,
                exam_code_22,
                exam_grade_22,
                irregularity_code_1_22,
                irregularity_code_2_22
            ) as 22,
            (
                admin_year_23,
                exam_code_23,
                exam_grade_23,
                irregularity_code_1_23,
                irregularity_code_2_23
            ) as 23,
            (
                admin_year_24,
                exam_code_24,
                exam_grade_24,
                irregularity_code_1_24,
                irregularity_code_2_24
            ) as 24,
            (
                admin_year_25,
                exam_code_25,
                exam_grade_25,
                irregularity_code_1_25,
                irregularity_code_2_25
            ) as 25,
            (
                admin_year_26,
                exam_code_26,
                exam_grade_26,
                irregularity_code_1_26,
                irregularity_code_2_26
            ) as 26,
            (
                admin_year_27,
                exam_code_27,
                exam_grade_27,
                irregularity_code_1_27,
                irregularity_code_2_27
            ) as 27,
            (
                admin_year_28,
                exam_code_28,
                exam_grade_28,
                irregularity_code_1_28,
                irregularity_code_2_28
            ) as 28,
            (
                admin_year_29,
                exam_code_29,
                exam_grade_29,
                irregularity_code_1_29,
                irregularity_code_2_29
            ) as 29,
            (
                admin_year_30,
                exam_code_30,
                exam_grade_30,
                irregularity_code_1_30,
                irregularity_code_2_30
            ) as 30
        )
    )
left join
    {{ ref("stg_collegeboard__ap_codes") }} as c1
    on exam_code = c1.code
    and c1.`domain` = 'Exam Codes'
left join
    {{ ref("stg_collegeboard__ap_codes") }} as c2
    on exam_code = c2.code
    and c2.`domain` = 'Irregularity Scores'
left join
    {{ ref("stg_collegeboard__ap_codes") }} as c3
    on exam_code = c3.code
    and c3.`domain` = 'Irregularity Scores'
left join
    {{ ref("stg_collegeboard__ap_id_crosswalk") }} as x
    on ap_number_ap_id = x.college_board_id
