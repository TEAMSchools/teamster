select
    s.id as studentid,
    s.student_number,
    s.family_ident,

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
from {{ ref("stg_powerschool__students") }} as s
inner join
    {{ ref("stg_powerschool__studentcontactassoc") }} as sca on s.dcid = sca.studentdcid
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
    s.id as studentid,
    s.student_number,
    s.family_ident,

    p.id as personid,

    0 as contactpriorityorder,

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
    {{ ref("stg_powerschool__person") }} as p on s.person_id = p.id and p.isactive = 1
