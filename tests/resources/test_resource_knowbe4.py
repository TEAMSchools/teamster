from dagster import EnvVar, build_resources

from teamster.libraries.knowbe4.resources import KnowBe4Resource


def test_knowbe4_resource():
    with build_resources(
        {
            "knowbe4": KnowBe4Resource(
                api_key=EnvVar("KNOWBE4_API_KEY"), server="us", page_size=500
            )
        }
    ) as resources:
        knowbe4: KnowBe4Resource = resources.knowbe4
