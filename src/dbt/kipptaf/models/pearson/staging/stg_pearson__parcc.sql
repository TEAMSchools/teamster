with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_pearson", model.name),
                    source("kippcamden_pearson", model.name),
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
                        coalesce(
                            cast(
                                safe.parse_datetime(
                                    '%m/%d/%Y %H:%M', unit1onlineteststartdatetime
                                ) as timestamp
                            ),
                            cast('9999-12-31' as timestamp)
                        ),
                        coalesce(
                            cast(
                                safe.parse_datetime(
                                    '%m/%d/%Y %H:%M', unit2onlineteststartdatetime
                                ) as timestamp
                            ),
                            cast('9999-12-31' as timestamp)
                        ),
                        coalesce(
                            cast(
                                safe.parse_datetime(
                                    '%m/%d/%Y %H:%M', unit3onlineteststartdatetime
                                ) as timestamp
                            ),
                            cast('9999-12-31' as timestamp)
                        ),
                        coalesce(
                            cast(
                                safe.parse_datetime(
                                    '%m/%d/%Y %H:%M', unit4onlineteststartdatetime
                                ) as timestamp
                            ),
                            cast('9999-12-31' as timestamp)
                        )
                    )
                )
        end,
        date(safe.parse_datetime('%m/%d/%Y %H:%M', attemptcreatedate))
    ) as test_date,
from union_relations
