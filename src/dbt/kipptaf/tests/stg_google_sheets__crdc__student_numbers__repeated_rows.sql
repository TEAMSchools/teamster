-- depends_on: {{ ref("stg_google_sheets__crdc__student_numbers") }}
-- reads the sheet: the staging model dedups these rows
select student_number, crdc_question_section, count(*) as n_rows,
from {{ source("google_sheets", "src_google_sheets__crdc__student_numbers") }}
group by student_number, crdc_question_section
having count(*) > 1
