{% set ref_form = ref("int_google_forms__form") %}
{% set ref_responses = ref("stg_google_forms__responses") %}
{% set ref_text_answers = ref("stg_google_forms__responses__answers__text_answers") %}
{% set ref_file_uploads = ref(
    "stg_google_forms__responses__answers__file_upload_answers"
) %}

with
    form_responses as (
        select
            {{ dbt_utils.star(from=ref_form, relation_alias="f") }},

            {{
                dbt_utils.star(
                    from=ref_responses,
                    relation_alias="r",
                    except=["form_id", "answers"],
                )
            }},

            {{
                dbt_utils.star(
                    from=ref_text_answers,
                    relation_alias="rata",
                    except=["form_id", "item_id", "question_id", "response_id"],
                    prefix="text_",
                )
            }},

            {{
                dbt_utils.star(
                    from=ref_file_uploads,
                    relation_alias="rafu",
                    except=["form_id", "item_id", "question_id", "response_id"],
                    prefix="file_upload_",
                )
            }},

            row_number() over (
                partition by f.form_id, r.respondent_email, rata.is_null_value
                order by r.last_submitted_time desc
            ) as rn_form_item_respondent_submitted_desc,
        from {{ ref_form }} as f
        left join {{ ref_responses }} as r on f.form_id = r.form_id
        left join
            {{ ref_text_answers }} as rata
            on f.form_id = rata.form_id
            and f.question_id = rata.question_id
            and r.response_id = rata.response_id
        left join
            {{ ref_file_uploads }} as rafu
            on f.form_id = rafu.form_id
            and f.question_id = rafu.question_id
            and r.response_id = rafu.response_id
    )

select
    *,

    timestamp(last_submitted_time) as last_submitted_timestamp,
    timestamp(create_time) as create_timestamp,

    date(
        timestamp(last_submitted_time), '{{ var("local_timezone") }}'
    ) as last_submitted_date_local,

    safe_cast(
        regexp_extract(
            max(if(item_abbreviation = 'respondent_name', text_value, null)) over (
                partition by response_id, respondent_email
            ),
            r'(\d{6})'
        ) as int
    ) as employee_number,
from form_responses
