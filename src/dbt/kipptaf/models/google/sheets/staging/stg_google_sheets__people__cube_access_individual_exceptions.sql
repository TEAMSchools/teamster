select
    * except (google_email),

    -- Cube resolves a viewer with a case-sensitive `google_email = @email`
    -- match against the JWT's own email claim (src/cube/cube.js), and this
    -- sheet is typed by hand. Fold case and strip padding once here so a
    -- `Jane@Apps.Teamschools.Org` entry grants what it says instead of
    -- matching nothing and denying silently.
    lower(trim(google_email)) as google_email,
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__people__cube_access_individual_exceptions",
        )
    }}
where google_email is not null and trim(google_email) != ''
