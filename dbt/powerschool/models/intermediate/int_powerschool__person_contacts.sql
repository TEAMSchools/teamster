/* address */
select
    paa.personid,
    paa.addresspriorityorder as priority_order,
    if(paa.addresspriorityorder = 1, 1, 0) as is_primary,

    acs.code as contact_type,

    concat(
        pa.street,
        if(pa.unit != '', ' ' || pa.unit, ''),
        ', ',
        pa.city,
        ', ',
        scs.code,
        ' ',
        pa.postalcode
    ) as contact,

    'Address' as contact_category,
from {{ ref("stg_powerschool__personaddressassoc") }} as paa
inner join
    {{ ref("stg_powerschool__codeset") }} as acs
    on paa.addresstypecodesetid = acs.codesetid
inner join
    {{ ref("stg_powerschool__personaddress") }} as pa
    on paa.personaddressid = pa.personaddressid
inner join
    {{ ref("stg_powerschool__codeset") }} as scs on pa.statescodesetid = scs.codesetid

union all

/* phone number */
select
    ppna.personid,
    ppna.phonenumberpriorityorder as priority_order,
    ppna.ispreferred as is_primary,

    pncs.code as contact_type,

    concat(
        '(',
        left(pn.phonenumber, 3),
        ') ',
        substring(pn.phonenumber, 4, 3),
        '-',
        substring(pn.phonenumber, 7, 4),
        if(pn.phonenumberext != '', ' x' || pn.phonenumberext, '')
    ) as contact,

    'Phone' as contact_category,
from {{ ref("stg_powerschool__personphonenumberassoc") }} as ppna
inner join
    {{ ref("stg_powerschool__codeset") }} as pncs
    on ppna.phonetypecodesetid = pncs.codesetid
inner join
    {{ ref("stg_powerschool__phonenumber") }} as pn
    on ppna.phonenumberid = pn.phonenumberid

union all

/* email */
select
    peaa.personid,
    peaa.emailaddresspriorityorder as priority_order,
    peaa.isprimaryemailaddress as is_primary,

    if(eacs.code = 'Not Set', 'Current', eacs.code) as contact_type,

    ea.emailaddress as contact,

    'Email' as contact_category,
from {{ ref("stg_powerschool__personemailaddressassoc") }} as peaa
inner join
    {{ ref("stg_powerschool__codeset") }} as eacs
    on peaa.emailtypecodesetid = eacs.codesetid
inner join
    {{ ref("stg_powerschool__emailaddress") }} as ea
    on peaa.emailaddressid = ea.emailaddressid
