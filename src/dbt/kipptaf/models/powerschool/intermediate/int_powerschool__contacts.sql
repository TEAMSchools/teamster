-- Only Miami still sources contacts from PowerSchool; the NJ regions (Newark,
-- Camden, Paterson) are Finalsite-sourced, so their PowerSchool contacts chain
-- (int_powerschool__contacts and upstreams) is disabled (#4346). Add a region
-- back here if it reverts to the PowerSchool branch.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_powerschool", "int_powerschool__contacts"),
                ]
            )
        }}
    )

select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
from union_relations as ur
