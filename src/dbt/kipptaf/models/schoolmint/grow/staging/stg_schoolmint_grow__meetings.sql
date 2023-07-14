with
    source as (
        select * from {{ source("schoolmint_grow", "src_schoolmint_grow__meetings") }}
    ),
    renamed as (
        select
            {{ adapter.quote("_id") }},
            {{ adapter.quote("name") }},
            {{ adapter.quote("district") }},
            {{ adapter.quote("created") }},
            {{ adapter.quote("lastModified") }},
            {{ adapter.quote("archivedAt") }},
            {{ adapter.quote("course") }},
            {{ adapter.quote("enablePhases") }},
            {{ adapter.quote("grade") }},
            {{ adapter.quote("isOpenToParticipants") }},
            {{ adapter.quote("isTemplate") }},
            {{ adapter.quote("isWeeklyDataMeeting") }},
            {{ adapter.quote("locked") }},
            {{ adapter.quote("meetingtag1") }},
            {{ adapter.quote("meetingtag2") }},
            {{ adapter.quote("meetingtag3") }},
            {{ adapter.quote("meetingtag4") }},
            {{ adapter.quote("private") }},
            {{ adapter.quote("school") }},
            {{ adapter.quote("signatureRequired") }},
            {{ adapter.quote("title") }},
            {{ adapter.quote("observations") }},
            {{ adapter.quote("date") }},
            {{ adapter.quote("actionSteps") }},
            {{ adapter.quote("onleave") }},
            {{ adapter.quote("offweek") }},
            {{ adapter.quote("unable") }},
            {{ adapter.quote("creator") }},
            {{ adapter.quote("participants") }},
            {{ adapter.quote("type") }},
            {{ adapter.quote("additionalFields") }},
            {{ adapter.quote("_dagster_partition_key") }}

        from source
    )
select *
from renamed
