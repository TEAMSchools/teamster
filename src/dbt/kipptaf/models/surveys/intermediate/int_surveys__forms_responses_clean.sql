SELECT * --clean this up
FROM {{ ref("base_google_forms__form_responses") }} as fr
INNER JOIN {{ ref("src_google_forms__form_items_extension")}} as fi
ON fr.form_id = fi.form_id
AND fr.item_id = fi.question_id