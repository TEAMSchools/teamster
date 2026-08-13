{% macro focus_phone_type(column) %}
    {#-
      Map a free-typed Finalsite phone type to the Focus display vocabulary.
      A blank or unrecognized type defaults to Cell Phone rather than dropping
      the contact (#4769 decision J).
    -#}
    case
        when lower(trim({{ column }})) in ('cell', 'mobile')
        then 'Cell Phone'
        when lower(trim({{ column }})) = 'home'
        then 'Home Phone'
        when lower(trim({{ column }})) in ('work', 'business', 'office')
        then 'Work Phone'
        when lower(trim({{ column }})) = 'workplace'
        then 'Workplace'
        when lower(trim({{ column }})) in ('alternate', 'day', 'daytime')
        then 'Alternate Phone'
        else 'Cell Phone'
    end
{% endmacro %}
