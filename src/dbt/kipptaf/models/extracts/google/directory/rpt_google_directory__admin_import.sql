select
    google_email,
    home_work_location_powerschool_school_id,
    case
    home_work_location_dagster_code_location
    when 'kippnewark' then '/Students/TEAM/'
    when 'kippcamden' then '/Students/KCNA/'
    when 'kippmiami' then '/Students/Miami/'
    end as ou_region,
    case
        home_work_location_powerschool_school_id
        /* TEAM */
        when 133570965
        then 'TEAM Academy'
        when 73252
        then 'Rise'
        when 73253
        then 'NCA'
        when 73254
        then 'SPARK'
        when 73255
        then 'THRIVE'
        when 73256
        then 'Seek'
        when 73257
        then 'Life'
        when 73258
        then 'BOLD'
        when 73259
        then 'Upper Roseville'
        when 732511
        then 'Newark Lab'
        when 732513
        then 'KJA'
        when 732514
        then 'KPA'
        /* KCNA */
        when 179901
        then 'LSP'
        when 179902
        then 'LSM'
        when 179903
        then 'KHM'
        when 179904
        then 'KCNHS'
        when 179905
        then 'KSE'
        /* KMS */
        when 30200803
        then 'Courage'
        when 30200804
        then 'Royalty Academy'
    end as ou_school
from {{ ref("base_people__staff_roster") }}
where
    user_principal_name is not null
    and assignment_status not in ('Terminated', 'Deceased')
    and home_work_location_powerschool_school_id != 0
