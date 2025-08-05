from dagster import EnvVar, build_resources

from teamster.libraries.couchdrop.resources import CouchdropResource


def build_couchdrop_resource() -> CouchdropResource:
    with build_resources(
        {
            "couchdrop": CouchdropResource(
                username=EnvVar("COUCHDROP_API_USERNAME"),
                password=EnvVar("COUCHDROP_API_PASSWORD"),
            )
        }
    ) as resources:
        return resources.couchdrop


def test_couchdrop_file_ls():
    couchdrop = build_couchdrop_resource()

    post_response = couchdrop.post(resource="file/ls", data={"path": "/"}).json()
    print(post_response)


def test_couchdrop_file_lstat():
    couchdrop = build_couchdrop_resource()

    post_response = couchdrop.post(resource="file/lstat", data={"path": "/"}).json()
    print(post_response)


def test_couchdrop_file_ls_r():
    couchdrop = build_couchdrop_resource()

    files = couchdrop.ls_r(path="/data-team")
    print(files)
