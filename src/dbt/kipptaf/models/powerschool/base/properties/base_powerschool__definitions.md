{% docs _dbt_source_relation %}

This field should be used when joining tables/views for performance purposes,
and to ensure the data joined belongs to the correct region.

{% enddocs %}

{% docs studentid %}

The internal PowerSchool ID for a student. This is not unique across regions. If
joining on this field, \_dbt_source_relation must also be used as part of the
join.

{% enddocs %}

{% docs students_dcid %}

The DCID (District Code ID) for the student's record. This is not unique across
regions. If joining on this field, \_dbt_source_relation must also be used as
part of the join.

{% enddocs %}

{% docs student_number %}

Unique student identifier. Source: `stg_powerschool__students`. For students
registered during and after the 2018-19 school year, the student_number is 6
digits in length, with the first digit indicating the student's region:

1. Newark
2. Camden
3. Miami

Even though this field is unique across regions, \_dbt_source_relation should
still be used as part of a join for query performance reasons.

{% enddocs %}

{% docs reenrollments_dcid %}

The DCID (District Code ID) for the student's re-enrollment record. This is not
unique across regions. If joining on this field, \_dbt_source_relation must also
be used as part of the join.

{% enddocs %}

{% docs grade_level %}

The numeric version of a student's grade level (with 0 for KG).

{% enddocs %}

{% docs schoolid %}

The school_number of the associated schools record.

{% enddocs %}

{% docs entrydate %}

The school enrollment entry date from the student table.

{% enddocs %}

{% docs exitdate %}

The school enrollment exit date from the student table.

{% enddocs %}
