select email, cast(student_number as int) as student_number,
from {{ source("powerschool_sftp", "src_powerschool__student_email") }}
