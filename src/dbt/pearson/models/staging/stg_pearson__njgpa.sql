{%- set src_njgpa = source("pearson", "src_pearson__njgpa") -%}

select
    {{
        dbt_utils.star(
            from=src_njgpa,
            except=[
                "staffmemberidentifier",
                "testadministrator",
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
                "filler3",
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
                "fillerfield_2",
                "fillerfield_3",
                "fillerfield_4",
                "fillerfield_5",
                "fillerfield_6",
                "fillerfield_7",
                "fillerfield_8",
                "fillerfield_9",
                "fillerfield",
                "filler33",
                "filler39",
                "filler35",
                "filler34",
                "filler30",
                "filler32",
                "filler38",
                "filler29",
                "filler37",
                "filler28",
                "filler27",
                "filler36",
                "filler31",
            ],
        )
    }},

    safe_cast(
        coalesce(
            staffmemberidentifier.long_value, staffmemberidentifier.double_value
        ) as int
    ) as staffmemberidentifier,
    safe_cast(
        coalesce(testadministrator.long_value, testadministrator.double_value) as int
    ) as testadministrator,

    safe_cast(left(assessmentyear, 4) as int) as academic_year,
from {{ src_njgpa }}
where summativeflag = 'Y' and testattemptednessflag = 'Y'
