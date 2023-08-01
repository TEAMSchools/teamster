select f.*, fi.*,
from {{ ref("stg_google_forms__form") }} as f
inner join {{ ref("stg_google_forms__form_items") }} as fi on f.form_id = fi.form_id
