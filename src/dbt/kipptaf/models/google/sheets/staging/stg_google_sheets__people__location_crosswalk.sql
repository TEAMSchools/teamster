with
    -- grain projection, not dup-masking: 1 row per distinct name and clean_name
    crosswalk_pairs as (
        select name, clean_name, count(*) over (partition by name) as n_clean_names,
        from
            {{
                source(
                    "google_sheets", "src_google_sheets__people__location_crosswalk"
                )
            }}
        where name is not null
        group by name, clean_name
    )

select name, clean_name,
from crosswalk_pairs
-- a name mapped to 2 clean_names has no correct pick, so it is dropped
where n_clean_names = 1
