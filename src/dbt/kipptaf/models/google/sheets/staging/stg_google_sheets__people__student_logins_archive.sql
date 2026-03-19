select *, username || '@teamstudents.org' as google_email,
from {{ source("google_sheets", "src_google_sheets__people__student_logins_archive") }}
