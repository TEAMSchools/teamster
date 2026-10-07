with
    checked as (
        select
            student_number,
            discipline,
            pathway_code,
            test_type,
            final_grad_path_name,

            test_type is distinct from final_grad_path_name as labels_disagree,
        from {{ ref("int_students__graduation_path_codes") }}
        where pathway_code in ('M', 'N', 'O', 'P')
    )

select student_number, discipline, pathway_code, test_type, final_grad_path_name,
from checked
where labels_disagree
