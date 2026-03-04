with
    contacts as (
        select
            sca.studentdcid,
            sca.personid,
            sca.contactpriorityorder,

            p.firstname,
            p.lastname,

            scd.isemergency,
            scd.iscustodial,
            scd.liveswithflg,
            scd.schoolpickupflg,

            sccs.code as relationship_type,

            coalesce(
                ocm.originalcontacttype, concat('contact', sca.contactpriorityorder)
            ) as person_type,
        from {{ ref("stg_powerschool__studentcontactassoc") }} as sca
        inner join {{ ref("stg_powerschool__person") }} as p on sca.personid = p.id
        inner join
            {{ ref("stg_powerschool__studentcontactdetail") }} as scd
            on sca.studentcontactassocid = scd.studentcontactassocid
            and scd.isactive = 1
        inner join
            {{ ref("stg_powerschool__codeset") }} as sccs
            on scd.relationshiptypecodesetid = sccs.codesetid
        left join
            {{ ref("stg_powerschool__originalcontactmap") }} as ocm
            on sca.studentcontactassocid = ocm.studentcontactassocid

        union all

        select
            s.dcid as studentdcid,

            p.id as personid,

            null as contactpriorityorder,

            p.firstname,
            p.lastname,

            0 as isemergency,
            0 as iscustodial,
            0 as liveswithflg,
            0 as schoolpickupflg,
            'Self' as relationship_type,
            'self' as person_type,
        from {{ ref("stg_powerschool__students") }} as s
        inner join
            {{ ref("stg_powerschool__person") }} as p
            on s.person_id = p.id
            and p.isactive = 1
    )

select
    * except (contactpriorityorder),

    concat(ltrim(rtrim(firstname)), ' ', ltrim(rtrim(lastname))) as contact_name,

    row_number() over (
        partition by studentdcid order by contactpriorityorder nulls last
    ) as contactpriorityorder,
from contacts
