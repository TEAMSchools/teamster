with
    transformations as (
        select
            `name`,
            address,
            pscomm_path,
            abbreviation,
            activecrslist,
            bulletinemail,
            sysemailfrom,
            tchrlogentrto,
            portalid,
            schooladdress,
            schoolcity,
            schoolstate,
            schoolzip,
            schoolphone,
            schoolfax,
            schoolcountry,
            principal,
            principalphone,
            principalemail,
            asstprincipalphone,
            asstprincipalemail,
            countyname,
            countynbr,
            asstprincipal,
            schedulewhichschool,
            schoolinfo_guid,
            sif_stateprid,
            psguid,
            ip_address,
            whomodifiedtype,
            transaction_date,

            cast(dcid as int) as dcid,
            cast(id as int) as id,
            cast(district_number as int) as district_number,
            cast(school_number as int) as school_number,
            cast(low_grade as int) as low_grade,
            cast(high_grade as int) as high_grade,
            cast(sortorder as int) as sortorder,
            cast(schoolgroup as int) as schoolgroup,
            cast(hist_low_grade as int) as hist_low_grade,
            cast(hist_high_grade as int) as hist_high_grade,
            cast(dfltnextschool as int) as dfltnextschool,
            cast(view_in_portal as int) as view_in_portal,
            cast(state_excludefromreporting as int) as state_excludefromreporting,
            cast(alternate_school_number as int) as alternate_school_number,
            cast(fee_exemption_status as int) as fee_exemption_status,
            cast(issummerschool as int) as issummerschool,
            cast(schoolcategorycodesetid as int) as schoolcategorycodesetid,
            cast(whomodifiedid as int) as whomodifiedid,
        from {{ source("powerschool_dlt", "schools") }}
    )

select
    *,

    case
        when high_grade = 12
        then 'HS'
        when high_grade = 8
        then 'MS'
        when high_grade in (4, 5)
        then 'ES'
    end as school_level,
from transformations
