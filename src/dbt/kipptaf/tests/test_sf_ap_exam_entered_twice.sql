-- depends_on: {{ ref("stg_kippadb__standardized_test") }}
with
    ranked as (
        select
            st.id,
            st.contact,
            st.date,
            st.subject,

            acc.ap_course_name,

            row_number() over (
                partition by st.contact, acc.ap_course_name, st.date
                order by st.last_modified_date desc, st.id desc
            ) as rn,
        from {{ ref("stg_kippadb__standardized_test") }} as st
        inner join
            {{ ref("stg_google_sheets__collegeboard__ap_course_crosswalk") }} as acc
            on st.subject = acc.test_name
            and acc.data_source = 'ADB'
        where
            st.test_type = 'Advanced Placement'
            and st.ap is not null
            and not st.scoring_irregularity
    )

select id, contact, `date`, `subject`, ap_course_name,
from ranked
where rn > 1
