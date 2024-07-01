with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                ]
            )
        }}
    )

select
    studentsdcid,
    fleid,
    newark_enrollment_number,
    infosnap_id,
    infosnap_opt_in,
    media_release,
    rides_staff,
    is_504,
from union_relations
