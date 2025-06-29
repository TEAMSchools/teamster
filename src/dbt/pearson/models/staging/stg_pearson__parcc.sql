{%- set src_parcc = source("pearson", "src_pearson__parcc") -%}

select
    {{
        dbt_utils.star(
            from=src_parcc,
            except=[
                "filler_1",
                "filler_10",
                "filler_11",
                "filler_2",
                "filler_3",
                "filler_4",
                "filler_5",
                "filler_6",
                "filler_7",
                "filler_8",
                "filler_9",
                "filler",
                "filler1",
                "filler10",
                "filler11",
                "filler12",
                "filler13",
                "filler14",
                "filler15",
                "filler16",
                "filler17",
                "filler18",
                "filler19",
                "filler2",
                "filler20",
                "filler21",
                "filler22",
                "filler23",
                "filler24",
                "filler25",
                "filler26",
                "filler27",
                "filler28",
                "filler29",
                "filler3",
                "filler30",
                "filler31",
                "filler32",
                "filler33",
                "filler34",
                "filler35",
                "filler36",
                "filler37",
                "filler38",
                "filler39",
                "filler4",
                "filler5",
                "filler6",
                "filler7",
                "filler8",
                "fillerfield_1",
                "fillerfield_10",
                "fillerfield_11",
                "fillerfield_12",
                "fillerfield_13",
                "fillerfield_14",
                "fillerfield_15",
                "fillerfield_16",
                "fillerfield_17",
                "fillerfield_18",
                "fillerfield_19",
                "fillerfield_2",
                "fillerfield_20",
                "fillerfield_21",
                "fillerfield_22",
                "fillerfield_23",
                "fillerfield_24",
                "fillerfield_25",
                "fillerfield_26",
                "fillerfield_27",
                "fillerfield_28",
                "fillerfield_29",
                "fillerfield_3",
                "fillerfield_30",
                "fillerfield_4",
                "fillerfield_5",
                "fillerfield_6",
                "fillerfield_7",
                "fillerfield_8",
                "fillerfield_9",
                "fillerfield",
                "fillerfield1",
                "fillerfield2",
                "fillerfield4",
                "fillerfield5",
                "fillerfield7",
                "shipreportdistrictcode",
                "shipreportschoolcode",
                "staffmemberidentifier",
                "statefield6",
                "statefield9",
                "testadministrator",
            ],
        )
    }},

    'PARCC' as assessment_name,

    coalesce(
        staffmemberidentifier.string_value,
        cast(staffmemberidentifier.double_value as string)
    ) as staffmemberidentifier,
    coalesce(
        testadministrator.string_value, cast(testadministrator.double_value as string)
    ) as testadministrator,
    coalesce(
        statefield6.string_value, cast(statefield6.double_value as string)
    ) as statefield6,
    coalesce(
        statefield9.string_value, cast(statefield9.double_value as string)
    ) as statefield9,
    coalesce(
        shipreportschoolcode.long_value, cast(shipreportschoolcode.double_value as int)
    ) as shipreportschoolcode,
    coalesce(
        shipreportdistrictcode.long_value,
        cast(shipreportdistrictcode.double_value as int)
    ) as shipreportdistrictcode,

    cast(left(assessmentyear, 4) as int) as academic_year,

    cast(regexp_extract(assessmentgrade, r'Grade\s(\d+)') as int) as test_grade,

    if(`subject` = 'English Language Arts/Literacy', 'ELA', 'Math') as discipline,

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
