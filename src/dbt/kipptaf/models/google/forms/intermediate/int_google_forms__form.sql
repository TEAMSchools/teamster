{% set ref_form = ref("stg_google_forms__form") %}
{% set ref_form_items = ref("stg_google_forms__form__items") %}
{% set src_form_items_ext = source(
    "google_forms", "src_google_forms__form_items_extension"
) %}

select
    {{ dbt_utils.star(from=ref_form, relation_alias="f") }},

    {{
        dbt_utils.star(
            from=ref_form_items, relation_alias="fi", except=["form_id"]
        )
    }},

    {{
        dbt_utils.star(
            from=src_form_items_ext,
            relation_alias="fie",
            except=["form_id", "item_id", "question_id", "title"],
            prefix="item_",
        )
    }},
from {{ ref_form }} as f
inner join {{ ref_form_items }} as fi on f.form_id = fi.form_id
left join
    {{ src_form_items_ext }} as fie
    on fi.form_id = fie.form_id
    and fi.item_id = fie.item_id
    and fi.question_item__question__question_id = fie.question_id
