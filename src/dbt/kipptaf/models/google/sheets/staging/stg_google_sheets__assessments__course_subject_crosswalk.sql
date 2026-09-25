select *,
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__assessments__course_subject_crosswalk",
        )
    }}
where powerschool_course_number is not null
