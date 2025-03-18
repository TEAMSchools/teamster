select source, question_code, response, response_int, response_string,
from {{ source("surveys", "src_surveys__scd_answer_crosswalk") }}
