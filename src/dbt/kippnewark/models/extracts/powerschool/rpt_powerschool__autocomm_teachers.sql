select
    teachernumber,
    first_name,
    last_name,
    loginid,
    teacherloginid,
    email_addr,
    schoolid,
    homeschoolid,
    `status`,
    teacherldapenabled,
    adminldapenabled,
    ptaccess,
    dob,
from {{ source("kipptaf_extracts", "rpt_powerschool__autocomm_teachers") }}
where home_work_location_dagster_code_location = '{{ project_name }}'
