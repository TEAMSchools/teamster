with
    principals as (
        -- ParentSquare wants the principal's given and family name as separate
        -- fields, but PowerSchool stores only one combined `principal` string
        -- that also carries honorifics ('Dr. Jane Doe'), so a whitespace split
        -- would put the honorific in first_name. Resolve the pair from the staff
        -- roster by email instead. `mail` is unique on the roster, so this
        -- cannot fan out.
        select
            given_name as principal_first_name,
            family_name_1 as principal_last_name,

            lower(mail) as principal_email_match,
        from {{ ref("int_people__staff_roster") }}
        where mail is not null
    ),

    schools as (
        select
            `name` as school_name,
            schooladdress as school_address,
            schoolcity as school_city,
            schoolstate as school_state,
            schoolzip as school_zip,
            principalemail as principal_email,

            cast(school_number as string) as school_id,
            lower(principalemail) as principal_email_match,

            -- PowerSchool holds school phones in mixed formats (bare digits and
            -- dash-separated); ParentSquare wants 10 digits.
            regexp_replace(schoolphone, r'[^0-9]', '') as school_phone,
        from {{ ref("stg_powerschool__schools") }}
        where _dbt_source_project = 'kippnewark' and state_excludefromreporting = 0
    )

select
    s.school_id,
    s.school_name,
    s.school_zip,
    s.school_address,
    s.school_city,
    s.school_state,
    s.principal_email,
    s.school_phone,

    p.principal_first_name,
    p.principal_last_name,
from schools as s
left join principals as p on s.principal_email_match = p.principal_email_match
