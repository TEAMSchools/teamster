from dagster import AssetExecutionContext, asset

from teamster.kipptaf.powerschool.enrollment.resources import (
    PowerSchoolEnrollmentResource,
)


@asset
def foo(context: AssetExecutionContext, ps_enrollment: PowerSchoolEnrollmentResource):
    data = ps_enrollment.get(endpoint="publishedactions")

    return data
