{% set ref_form = ref("int_google_forms__form") %}
{% set ref_responses = ref("stg_google_forms__responses") %}
{% set ref_text_answers = ref("stg_google_forms__responses__answers__text_answers") %}

select
    {{ dbt_utils.star(from=ref_form, relation_alias="f") }},

    {{
        dbt_utils.star(
            from=ref_responses, relation_alias="r", except=["form_id", "answers"]
        )
    }},

    {{
        dbt_utils.star(
            from=ref_text_answers,
            relation_alias="rata",
            except=["form_id", "item_id", "question_id", "response_id"],
        )
    }},

    row_number() over (
        partition by f.form_id, f.item_id, r.respondent_email, rata.is_null_value
        order by r.last_submitted_time desc
    ) as rn_form_item_respondent_submitted_desc
from {{ ref_form }} as f
left join {{ ref_responses }} as r on f.form_id = r.form_id
left join
    {{ ref_text_answers }} as rata
    on f.form_id = rata.form_id
    and f.question_item__question__question_id = rata.question_id
    and r.response_id = rata.response_id
