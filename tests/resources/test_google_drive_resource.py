from dagster import build_init_resource_context

from teamster.code_locations.kipptaf.resources import GOOGLE_DRIVE_RESOURCE


def test_google_forms_resource():
    GOOGLE_DRIVE_RESOURCE.setup_for_execution(context=build_init_resource_context())

    files = GOOGLE_DRIVE_RESOURCE.list_files(
        q="mimeType='application/vnd.google-apps.form' and '1ZJAXcPfmdTDmJCqcMRje0czrwR7cF6hC' in parents",
        corpora="drive",
        driveId="0AKZ2G1Z8rxooUk9PVA",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    )

    assert len(files) > 0
