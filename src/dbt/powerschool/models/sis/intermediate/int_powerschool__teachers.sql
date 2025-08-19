select
    u.* except (
        executionid,
        ip_address,
        psguid,
        transaction_date,
        whencreated,
        whenmodified,
        whocreated,
        whomodified,
        whomodifiedid,
        whomodifiedtype
    ),

    ss.* except (
        users_dcid,
        dcid,
        executionid,
        ip_address,
        psguid,
        transaction_date,
        whencreated,
        whenmodified,
        whocreated,
        whomodified,
        whomodifiedid,
        whomodifiedtype
    ),
from {{ ref("stg_powerschool__users") }} as u
inner join {{ ref("stg_powerschool__schoolstaff") }} as ss on u.dcid = ss.users_dcid
