select
    * except (
        google_email,
        additional_student_location_scope,
        additional_staff_location_scope,
        staff_department_scope,
        staff_pii_scope,
        staff_compensation_scope,
        staff_observations_scope,
        staff_benefits_scope
    ),

    -- Cube resolves a viewer with a case-sensitive `google_email = @email`
    -- match against the JWT's own email claim (src/cube/cube.js), and this
    -- sheet is typed by hand. Fold case and strip padding once here so a
    -- `Jane@Apps.Teamschools.Org` entry grants what it says instead of
    -- matching nothing and denying silently.
    lower(trim(google_email)) as google_email,

    -- Every cell in this sheet carries a word, so a Google Form can make each
    -- field required and nothing downstream has to guess at an empty cell.
    -- 'none' is that word for the two location axes, and NULL here means only
    -- "no grant on this axis".
    nullif(
        additional_student_location_scope, 'none'
    ) as additional_student_location_scope,
    nullif(additional_staff_location_scope, 'none') as additional_staff_location_scope,

    -- A row grants ONE location. The two axis columns say which axes reach it,
    -- and a test enforces that they agree whenever both are set, so the row's
    -- tier is simply whichever axis names it.
    coalesce(
        nullif(additional_student_location_scope, 'none'),
        nullif(additional_staff_location_scope, 'none')
    ) as additional_location_scope,

    -- The five remit columns are overrides, so they need two distinct ways to
    -- say nothing, and the sheet spells both: 'inherit' leaves the person's
    -- role- or department-derived setting alone, and 'none' REVOKES below it.
    -- 'inherit' becomes NULL because that is what the coalesce chain in
    -- dim_staff_cube_access reads as "fall through"; 'none' is passed straight
    -- through to win that coalesce. Blank would be indistinguishable from an
    -- unfilled cell, which is why neither means anything here.
    nullif(staff_department_scope, 'inherit') as staff_department_scope,
    nullif(staff_pii_scope, 'inherit') as staff_pii_scope,
    nullif(staff_compensation_scope, 'inherit') as staff_compensation_scope,
    nullif(staff_observations_scope, 'inherit') as staff_observations_scope,
    nullif(staff_benefits_scope, 'inherit') as staff_benefits_scope,
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__people__cube_access_individual_exceptions",
        )
    }}
where google_email is not null and trim(google_email) != ''
