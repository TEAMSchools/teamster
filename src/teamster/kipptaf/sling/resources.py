from dagster import EnvVar
from dagster_embedded_elt.sling.resources import SlingConnectionResource, SlingResource

sling_resource = SlingResource(
    connections=[
        SlingConnectionResource(
            name="MY_SNOWFLAKE",
            type="snowflake",
            host=EnvVar("SNOWFLAKE_HOST"),
            user=EnvVar("SNOWFLAKE_USER"),
            role="REPORTING",
        ),
    ]
)
