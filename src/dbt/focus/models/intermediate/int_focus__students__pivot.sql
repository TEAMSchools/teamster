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
        from {{ ref("stg_focus__students") }}
    ),

    unpivoted as (
        select student_id, column_name, option_id,
        from
            encoded unpivot (
                option_id for column_name in (
                    custom_100000105,
                    custom_100000104,
                    custom_100000102,
                    custom_100000101,
                    custom_200000000,
                    custom_100000100,
                    custom_100000103,
                    custom_837,
                    custom_200000005
                )
            )
    ),

    decoded as (
        select unpivoted.student_id, unpivoted.column_name, `options`.label,
        from unpivoted
        left join
            {{ ref("int_focus__custom_field_options") }} as `options`
            on unpivoted.column_name = `options`.column_name
            and unpivoted.option_id = `options`.option_id
            and `options`.source_class = 'SISStudent'
    )

select *,
from
    decoded pivot (
        any_value(label) for column_name in (
            'custom_100000105' as ethnicity_hispanic_or_latino_label,
            'custom_100000104' as race_white_label,
            'custom_100000102' as race_black_or_african_american_label,
            'custom_100000101' as race_asian_label,
            'custom_200000000' as sex_label,
            'custom_100000100' as race_american_indian_or_alaska_native_label,
            'custom_100000103' as race_native_hawaiian_or_other_pacific_islander_label,
            'custom_837' as residence_county_label,
            'custom_200000005' as language_label
        )
    )
