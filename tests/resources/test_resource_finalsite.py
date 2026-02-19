from dagster import EnvVar, build_resources

from teamster.libraries.finalsite.resources import FinalsiteResource


def test_finalsite_resource():
    from teamster.code_locations.kippnewark import CODE_LOCATION

    with build_resources(
        {
            "finalsite": FinalsiteResource(
                server=CODE_LOCATION,
                credential_id=EnvVar("FINALSITE_CREDENTIAL_ID_KIPPNEWARK"),
                secret=EnvVar("FINALSITE_SECRET_KIPPNEWARK"),
            )
        }
    ) as resources:
        finalsite: FinalsiteResource = resources.finalsite

    assert finalsite is not None

    response = finalsite.list(path="contacts")

    print(response)
