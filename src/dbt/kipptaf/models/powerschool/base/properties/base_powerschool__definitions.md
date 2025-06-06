{% docs _dbt_source_relation %}

This field should be used when joining tables/views for performance purposes, and to ensure the data joined belongs to the correct region.

{% enddocs %}

{% docs _dbt_source_relation %}

The internal PowerSchool ID for a student. This is not unique across regions. If joining on this field, _dbt_source_relation must also be used as part of the join.

{% enddocs %}
