with
    -- grain projection, not dup-masking: 1 row per distinct Name and Clean_Name
    crosswalk_pairs as (
        select `Name`, clean_name, count(*) over (partition by `Name`) as n_clean_names,
        from
            {{
                source(
                    "google_sheets", "src_google_sheets__people__location_crosswalk"
                )
            }}
        where `Name` is not null
        group by `Name`, clean_name
    )

select `Name`, clean_name as `Clean_Name`,
from crosswalk_pairs
-- a Name mapped to 2 Clean_Names has no correct pick, so it is dropped
where n_clean_names = 1
