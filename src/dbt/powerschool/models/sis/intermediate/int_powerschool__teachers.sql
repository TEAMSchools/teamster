select
    u.* except (ip_address, psguid, transaction_date, whomodifiedid, whomodifiedtype),

    ss.* except (
        users_dcid,
        dcid,
        ip_address,
        psguid,
        transaction_date,
        whomodifiedid,
        whomodifiedtype
    ),
from {{ ref("stg_powerschool__users") }} as u
inner join {{ ref("stg_powerschool__schoolstaff") }} as ss on u.dcid = ss.users_dcid
