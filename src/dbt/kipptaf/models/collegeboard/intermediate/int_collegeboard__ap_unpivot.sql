select
    ap_number_ap_id,

    /* unpivot cols */
    rn_exam_number,
    admin_year,
    exam_code,
    irregularity_code_1,
    irregularity_code_2,

    cast(exam_grade as int) as exam_grade,

    -- trunk-ignore-begin(sqlfluff/CV10)
    case
        exam_code
        when "07"
        then "United States History"
        when "10"
        then "African American Studies"
        when "13"
        then "Art History"
        when "14"
        then "Drawing"
        when "15"
        then "2-D Art and Design"
        when "16"
        then "3-D Art and Design"
        when "20"
        then "Biology"
        when "22"
        then "Seminar"
        when "23"
        then "Research"
        when "25"
        then "Chemistry"
        when "28"
        then "Chinese Language and Culture"
        when "31"
        then "Computer Science A"
        when "32"
        then "Computer Science Principles"
        when "33"
        then "Computer Science AB 2010"
        when "34"
        then "Microeconomics"
        when "35"
        then "Macroeconomics"
        when "36"
        then "English Language and Composition"
        when "37"
        then "English Literature and Composition"
        when "40"
        then "Environmental Science"
        when "43"
        then "European History"
        when "48"
        then "French Language and Culture"
        when "51"
        then "French Literature 2010"
        when "53"
        then "Human Geography"
        when "55"
        then "German Language and Culture"
        when "57"
        then "United States Government and Politics"
        when "58"
        then "Comparative Government and Politics"
        when "60"
        then "Latin"
        when "61"
        then "Latin Literature 2010"
        when "62"
        then "Italian Language and Culture"
        when "64"
        then "Japanese Language and Culture"
        when "65"
        then "Precalculus"
        when "66"
        then "Calculus AB"
        when "68"
        then "Calculus BC"
        when "69"
        then "Calculus BC: AB Subscore"
        when "75"
        then "Music Theory"
        when "76"
        then "Music Aural Subscore"
        when "77"
        then "Music Non-Aural Subscore"
        when "78"
        then "Physics B 2014"
        when "80"
        then "Physics C: Mechanics"
        when "82"
        then "Physics C: Electricity and Magnetism"
        when "83"
        then "Physics 1"
        when "84"
        then "Physics 2"
        when "85"
        then "Psychology"
        when "87"
        then "Spanish Language and Culture"
        when "89"
        then "Spanish Literature and Culture"
        when "90"
        then "Statistics"
        when "93"
        then "World History: Modern"
    end as exam_code_description,
    case
        when irregularity_code_1 = "01"
        then "Score not yet available - student will be contacted by 8/1"
        when irregularity_code_1 = "04"
        then "Score canceled - student's choice per options received"
        when irregularity_code_1 = "07"
        then "Pending student response to options provided"
        when irregularity_code_1 = "11"
        then "Score not available"
        when irregularity_code_1 = "16"
        then "No score available: Makeup exam was requested but not taken"
        when irregularity_code_1 = "17"
        then "Score Canceled: Makeup exam was requested but not taken"
        when irregularity_code_1 = "20"
        then "School reported undertiming of 5 minutes or less"
        when irregularity_code_1 = "34"
        then "School reported distraction during exam"
        when irregularity_code_1 = "37"
        then "Portion of exam lost - score projected from remainder"
        when irregularity_code_1 = "38"
        then "Media not scorable - score projected from remainder"
        when irregularity_code_1 = "39"
        then "School started exam late"
        when irregularity_code_1 = "40"
        then "School reported undertiming of more than 5 minutes"
        when irregularity_code_1 = "42"
        then "Portion unscorable - score projected from remainder"
        when irregularity_code_1 = "44"
        then "Score projected from multiple-choice section"
        when irregularity_code_1 = "51"
        then "Score projected from free-response section"
        when irregularity_code_1 = "57"
        then "Score projected from multiple-choice and free-resp. sections"
        when irregularity_code_1 = "66"
        then "School reported overtiming of more than 5 minutes"
        when irregularity_code_1 = "87"
        then "Score canceled due to missing portion of exam"
        when irregularity_code_1 = "91"
        then "One or more performance tasks not scored"
        when irregularity_code_1 = "94"
        then "Score canceled at student's request"
        when irregularity_code_1 = "95"
        then "Second exam canceled - was not authorized"
        when irregularity_code_1 = "96"
        then "Score not yet available"
        when irregularity_code_1 = "98"
        then "Score withheld on college report at student's request"
        when irregularity_code_1 in ("19", "92")
        then "Score canceled"
        when
            irregularity_code_1 in (
                "02"
                "03",
                "05",
                "06",
                "08",
                "09",
                "10",
                "12",
                "13",
                "14",
                "15",
                "18",
                "80",
                "81",
                "82",
                "83",
                "84",
                "85",
                "86",
                "88",
                "89",
                "90",
                "93",
                "97"
            )
        then "Score delayed - will be reported as soon as possible"
    end as irregularity_code_1_description,
    case
        when irregularity_code_2 = "01"
        then "Score not yet available - student will be contacted by 8/1"
        when irregularity_code_2 = "04"
        then "Score canceled - student's choice per options received"
        when irregularity_code_2 = "07"
        then "Pending student response to options provided"
        when irregularity_code_2 = "11"
        then "Score not available"
        when irregularity_code_2 = "16"
        then "No score available: Makeup exam was requested but not taken"
        when irregularity_code_2 = "17"
        then "Score Canceled: Makeup exam was requested but not taken"
        when irregularity_code_2 = "20"
        then "School reported undertiming of 5 minutes or less"
        when irregularity_code_2 = "34"
        then "School reported distraction during exam"
        when irregularity_code_2 = "37"
        then "Portion of exam lost - score projected from remainder"
        when irregularity_code_2 = "38"
        then "Media not scorable - score projected from remainder"
        when irregularity_code_2 = "39"
        then "School started exam late"
        when irregularity_code_2 = "40"
        then "School reported undertiming of more than 5 minutes"
        when irregularity_code_2 = "42"
        then "Portion unscorable - score projected from remainder"
        when irregularity_code_2 = "44"
        then "Score projected from multiple-choice section"
        when irregularity_code_2 = "51"
        then "Score projected from free-response section"
        when irregularity_code_2 = "57"
        then "Score projected from multiple-choice and free-resp. sections"
        when irregularity_code_2 = "66"
        then "School reported overtiming of more than 5 minutes"
        when irregularity_code_2 = "87"
        then "Score canceled due to missing portion of exam"
        when irregularity_code_2 = "91"
        then "One or more performance tasks not scored"
        when irregularity_code_2 = "94"
        then "Score canceled at student's request"
        when irregularity_code_2 = "95"
        then "Second exam canceled - was not authorized"
        when irregularity_code_2 = "96"
        then "Score not yet available"
        when irregularity_code_2 = "98"
        then "Score withheld on college report at student's request"
        when irregularity_code_2 in ("19", "92")
        then "Score canceled"
        when
            irregularity_code_2 in (
                "02"
                "03",
                "05",
                "06",
                "08",
                "09",
                "10",
                "12",
                "13",
                "14",
                "15",
                "18",
                "80",
                "81",
                "82",
                "83",
                "84",
                "85",
                "86",
                "88",
                "89",
                "90",
                "93",
                "97"
            )
        then "Score delayed - will be reported as soon as possible"
    end as irregularity_code_2_description,
-- trunk-ignore-end(sqlfluff/CV10)
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
