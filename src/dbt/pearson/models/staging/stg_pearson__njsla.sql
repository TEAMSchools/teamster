{%- set src_parcc = source("pearson", "src_pearson__njsla") -%}

select
    {{
        dbt_utils.star(
            from=src_parcc,
            except=[
                "filler_1",
                "filler_10",
                "filler_11",
                "filler_12",
                "filler_13",
                "filler_14",
                "filler_15",
                "filler_16",
                "filler_17",
                "filler_18",
                "filler_19",
                "filler_2",
                "filler_20",
                "filler_21",
                "filler_22",
                "filler_23",
                "filler_24",
                "filler_25",
                "filler_26",
                "filler_27",
                "filler_28",
                "filler_29",
                "filler_3",
                "filler_30",
                "filler_31",
                "filler_32",
                "filler_33",
                "filler_34",
                "filler_35",
                "filler_36",
                "filler_37",
                "filler_38",
                "filler_39",
                "filler_4",
                "filler_40",
                "filler_41",
                "filler_42",
                "filler_43",
                "filler_44",
                "filler_45",
                "filler_46",
                "filler_47",
                "filler_48",
                "filler_49",
                "filler_5",
                "filler_50",
                "filler_51",
                "filler_52",
                "filler_53",
                "filler_54",
                "filler_55",
                "filler_56",
                "filler_57",
                "filler_58",
                "filler_59",
                "filler_6",
                "filler_60",
                "filler_61",
                "filler_62",
                "filler_63",
                "filler_64",
                "filler_65",
                "filler_66",
                "filler_67",
                "filler_68",
                "filler_69",
                "filler_7",
                "filler_70",
                "filler_71",
                "filler_72",
                "filler_73",
                "filler_74",
                "filler_75",
                "filler_76",
                "filler_77",
                "filler_78",
                "filler_79",
                "filler_8",
                "filler_80",
                "filler_81",
                "filler_82",
                "filler_83",
                "filler_84",
                "filler_85",
                "filler_9",
                "filler",
                "staffmemberidentifier",
                "testadministrator",
                "englishlearnerel",
                "multilinguallearnerml",
            ],
        )
    }},

    'NJSLA' as assessment_name,

    cast(staffmemberidentifier as string) as staffmemberidentifier,
    cast(testadministrator as string) as testadministrator,

    cast(left(assessmentyear, 4) as int) as academic_year,

    cast(regexp_extract(assessmentgrade, r'Grade\s(\d+)') as int) as test_grade,

    coalesce(multilinguallearnerml, englishlearnerel) as englishlearnerel,

    if(
        `subject` in ('English Language Arts', 'English Language Arts/Literacy'),
        'ELA',
        'Math'
    ) as discipline,
    if(testperformancelevel >= 4, true, false) as is_proficient,

    if(testperformancelevel <= 2, true, false) as is_bl_fb,

    case
        testperformancelevel
        when 5
        then 'Exceeded Expectations'
        when 4
        then 'Met Expectations'
        when 3
        then 'Approached Expectations'
        when 2
        then 'Partially Met Expectations'
        when 1
        then 'Did Not Yet Meet Expectations'
    end as testperformancelevel_text,
from {{ src_parcc }}
where summativeflag = 'Y' and testattemptednessflag = 'Y'
