select
    cast(school_number as string) as school_id,
    name as school_name,
    cast(school_number as string) as school_number,
    null as state_id,
    if(low_grade = 0, 'Kindergarten', cast(low_grade as string)) as low_grade,
    cast(high_grade as string) as high_grade,
    principal as principal,
    principalemail as principal_email,
    schooladdress as school_address,
    schoolcity as school_city,
    schoolstate as school_state,
    schoolzip as school_zip,
    null as school_phone,
from {{ ref("stg_powerschool__schools") }}
where
    /* filter out summer school and graduated students */
    state_excludefromreporting = 0

union all

select
    '0' as school_id,
    'District Office' as school_name,
    '0' as school_number,
    null as state_id,
    'Kindergarten' as low_grade,
    '12' as high_grade,
    'Ryan Hill' as principal,
    'rhill@kippteamandfamily.org' as principal_email,
    '60 Park Place, Suite 802' as school_address,
    'Newark' as school_city,
    'NJ' as school_state,
    '07102' as school_zip,
    null as school_phone,
