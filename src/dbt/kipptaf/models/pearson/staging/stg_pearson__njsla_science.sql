with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_pearson", "stg_pearson__njsla_science"),
                    source("kippcamden_pearson", "stg_pearson__njsla_science"),
                    source("kipppaterson_pearson", "int_pearson__njsla_science"),
                ]
            )
        }}
    )

select
    *,

    if(
        `subject` = 'English Language Arts/Literacy', 'English Language Arts', `subject`
    ) as subject_area,

    if(`period` = 'FallBlock', 'Fall', `period`) as administration_period,

    {{ extract_code_location("union_relations") }} as _dbt_source_project,

    case
        testcode
        when 'SC05'
        then 'SCI05'
        when 'SC08'
        then 'SCI08'
        when 'SC11'
        then 'SCI11'
        else testcode
    end as module_code,

    coalesce(
        case
            when
                coalesce(
                    unit1onlineteststartdatetime,
                    unit2onlineteststartdatetime,
                    unit3onlineteststartdatetime,
                    unit4onlineteststartdatetime
                )
                is not null
            then
                date(
                    least(
                        -- safe_cast fails on no-seconds strings (e.g. '2022-05-10
                        -- 09:26');
                        -- safe.parse_datetime('%Y-%m-%d %H:%M', ...) is load-bearing
                        -- for that format
                        coalesce(
                            safe_cast(unit1onlineteststartdatetime as timestamp),
                            cast(
                                safe.parse_datetime(
                                    '%Y-%m-%d %H:%M', unit1onlineteststartdatetime
                                ) as timestamp
                            ),
                            cast('9999-12-31' as timestamp)
                        ),
                        coalesce(
                            safe_cast(unit2onlineteststartdatetime as timestamp),
                            cast(
                                safe.parse_datetime(
                                    '%Y-%m-%d %H:%M', unit2onlineteststartdatetime
                                ) as timestamp
                            ),
                            cast('9999-12-31' as timestamp)
                        ),
                        coalesce(
                            safe_cast(unit3onlineteststartdatetime as timestamp),
                            cast(
                                safe.parse_datetime(
                                    '%Y-%m-%d %H:%M', unit3onlineteststartdatetime
                                ) as timestamp
                            ),
                            cast('9999-12-31' as timestamp)
                        ),
                        coalesce(
                            safe_cast(unit4onlineteststartdatetime as timestamp),
                            cast(
                                safe.parse_datetime(
                                    '%Y-%m-%d %H:%M', unit4onlineteststartdatetime
                                ) as timestamp
                            ),
                            cast('9999-12-31' as timestamp)
                        )
                    )
                )
        end,
        safe_cast(paperattemptcreatedate as date)
    ) as test_date,
from union_relations
