select st.*, c.school_specific_id,
from {{ ref("stg_kippadb__standardized_test") }} as st
inner join {{ ref("stg_kippadb__contact") }} as c on st.contact = c.id
