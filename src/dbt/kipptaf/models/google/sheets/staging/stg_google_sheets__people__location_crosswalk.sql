-- A Name listed twice with 1 Clean_Name collapses to 1 row. A Name mapped to 2
-- Clean_Names has no correct pick, so it is dropped until Ops fixes the sheet.
select lc.name as `Name`, any_value(lc.clean_name) as `Clean_Name`,
from
    {{ source("google_sheets", "src_google_sheets__people__location_crosswalk") }} as lc
group by lc.name
having count(distinct format('%T', lc.clean_name)) = 1
