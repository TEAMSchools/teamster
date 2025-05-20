select ccdcid, avg(enrolledcredits) as enrolledcredits,
from {{ source("powerschool", "src_powerschool__gpprogresssubjectenrolled") }}
