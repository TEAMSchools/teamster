select
    * except (
        google_email, additional_student_location_scope, additional_staff_location_scope
    ),

    -- Cube resolves a viewer with a case-sensitive `google_email = @email`
    -- match against the JWT's own email claim (src/cube/cube.js), and this
    -- sheet is typed by hand. Fold case and strip padding once here so a
    -- `Jane@Apps.Teamschools.Org` entry grants what it says instead of
    -- matching nothing and denying silently.
    lower(trim(google_email)) as google_email,

    -- A blank cell and the literal 'none' both mean "this axis gets nothing
    -- from this row". Collapse them once here so every consumer tests for NULL
    -- and nothing has to know both spellings. 'none' is accepted at all because
    -- it is the word the role and department sheets use for the same idea.
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
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__people__cube_access_individual_exceptions",
        )
    }}
where google_email is not null and trim(google_email) != ''
