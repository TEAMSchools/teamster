with
    current_record as (
        select
            associate_oid,
            business_communication__emails,
            business_communication__landlines,
            business_communication__mobiles,
            person__communication__emails,
            person__communication__landlines,
            person__communication__mobiles,
        from {{ ref("stg_adp_workforce_now__workers") }}
        where is_current_record
    )

select
    cr.associate_oid,

    c.itemid as item_id,

    c.namecode.codevalue as name_code__code_value,
    c.namecode.longname as name_code__long_name,
    c.namecode.shortname as name_code__short_name,
    c.namecode.effectivedate as name_code__effective_date,

    c.emailuri as email_uri,
    c.notificationindicator as notification_indicator,

    null as formatted_number,
    null as country_dialing,
    null as area_dialing,
    null as dial_number,
    null as `extension`,
    null as `access`,
from current_record as cr
cross join unnest(cr.business_communication__emails) as c

union all

select
    cr.associate_oid,

    c.itemid as item_id,

    c.namecode.codevalue as name_code__code_value,
    c.namecode.longname as name_code__long_name,
    c.namecode.shortname as name_code__short_name,
    c.namecode.effectivedate as name_code__effective_date,

    null as email_uri,
    null as notification_indicator,

    c.formattednumber as formatted_number,
    c.countrydialing as country_dialing,
    c.areadialing as area_dialing,
    c.dialnumber as dial_number,
    c.`extension`,
    c.`access`,
from current_record as cr
cross join unnest(cr.business_communication__landlines) as c

union all

select
    cr.associate_oid,

    c.itemid as item_id,

    c.namecode.codevalue as name_code__code_value,
    c.namecode.longname as name_code__long_name,
    c.namecode.shortname as name_code__short_name,
    c.namecode.effectivedate as name_code__effective_date,

    null as email_uri,
    null as notification_indicator,

    c.formattednumber as formatted_number,
    c.countrydialing as country_dialing,
    c.areadialing as area_dialing,
    c.dialnumber as dial_number,
    c.`extension`,
    c.`access`,
from current_record as cr
cross join unnest(cr.business_communication__mobiles) as c

union all

select
    cr.associate_oid,

    c.itemid as item_id,

    c.namecode.codevalue as name_code__code_value,
    c.namecode.longname as name_code__long_name,
    c.namecode.shortname as name_code__short_name,
    c.namecode.effectivedate as name_code__effective_date,

    c.emailuri as email_uri,
    c.notificationindicator as notification_indicator,

    null as formatted_number,
    null as country_dialing,
    null as area_dialing,
    null as dial_number,
    null as `extension`,
    null as `access`,
from current_record as cr
cross join unnest(cr.person__communication__emails) as c

union all

select
    cr.associate_oid,

    c.itemid as item_id,

    c.namecode.codevalue as name_code__code_value,
    c.namecode.longname as name_code__long_name,
    c.namecode.shortname as name_code__short_name,
    c.namecode.effectivedate as name_code__effective_date,

    null as email_uri,
    null as notification_indicator,

    c.formattednumber as formatted_number,
    c.countrydialing as country_dialing,
    c.areadialing as area_dialing,
    c.dialnumber as dial_number,
    c.`extension`,
    c.`access`,
from current_record as cr
cross join unnest(cr.person__communication__landlines) as c

union all

select
    cr.associate_oid,

    c.itemid as item_id,

    c.namecode.codevalue as name_code__code_value,
    c.namecode.longname as name_code__long_name,
    c.namecode.shortname as name_code__short_name,
    c.namecode.effectivedate as name_code__effective_date,

    null as email_uri,
    null as notification_indicator,

    c.formattednumber as formatted_number,
    c.countrydialing as country_dialing,
    c.areadialing as area_dialing,
    c.dialnumber as dial_number,
    c.`extension`,
    c.`access`,
from current_record as cr
cross join unnest(cr.person__communication__mobiles) as c
