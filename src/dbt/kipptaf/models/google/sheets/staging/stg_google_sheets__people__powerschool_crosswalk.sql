with
    crosswalk as (
        select
            *,

            is_active
            and employee_number is not null
            and countif(is_active) over (partition by employee_number)
            > 1 as is_duplicate_active,
        from
            {{
                source(
                    "google_sheets",
                    "src_google_sheets__people__powerschool_crosswalk",
                )
            }}
    )

-- 2 active rows for 1 employee number have no correct pick, so both are dropped
-- until Ops fixes the sheet. Inactive history rows stay.
select * except (is_duplicate_active),
from crosswalk
where is_duplicate_active is not true
