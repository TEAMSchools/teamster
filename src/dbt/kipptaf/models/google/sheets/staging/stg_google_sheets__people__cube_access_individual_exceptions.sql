select
    * except (google_email),

    -- Cube resolves a viewer with a case-sensitive `google_email = @email`
    -- match against the JWT's own email claim (src/cube/cube.js), and this
    -- sheet is typed by hand. Fold case and strip padding once here so a
    -- `Jane@Apps.Teamschools.Org` entry grants what it says instead of
    -- matching nothing and denying silently.
    lower(trim(google_email)) as google_email,

    -- Every other column passes through exactly as typed. The sheet's words --
    -- 'none' on a location axis, 'inherit' on a remit override -- are what the
    -- not_null and accepted_values tests here assert, so translating them to
    -- NULL at this layer would make those tests unsatisfiable. The translation
    -- belongs to dim_staff_cube_access, which is what consumes NULL as
    -- "fall through".
    --
    -- The one derived column: a row grants ONE location, the two axis columns
    -- say which axes reach it, and a test enforces that they agree whenever
    -- both name a tier. So the row's tier is whichever axis names one, and NULL
    -- means the row grants no location at all.
    coalesce(
        nullif(additional_student_location_scope, 'none'),
        nullif(additional_staff_location_scope, 'none')
    ) as additional_location_scope,

    -- Whether this row applies right now. Derived here so the rule has exactly
    -- one definition: the mart, both singular tests, and four config.where
    -- clauses all read this column instead of restating the comparison.
    -- A null on either date reads as NOT live. That is the opposite of what a
    -- missing bound would normally mean, and it is deliberate -- an access
    -- grant with no stated end is the shape you want to fail closed on. Both
    -- date columns carry an error-severity not_null, so a null here is already
    -- a broken row; this stops it granting anything while the test reports it.
    coalesce(
        status = 'active'
        and grant_date <= current_date('{{ var("local_timezone") }}')
        and expiry_date >= current_date('{{ var("local_timezone") }}'),
        false
    ) as is_live,
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__people__cube_access_individual_exceptions",
        )
    }}
where google_email is not null and trim(google_email) != ''
