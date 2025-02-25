select crdc_question_section, student_number,
from {{ source("crdc", "src_crdc__student_numbers") }}
