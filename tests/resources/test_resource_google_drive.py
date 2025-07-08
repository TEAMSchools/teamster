from dagster import build_resources

from teamster.libraries.google.drive.resources import GoogleDriveResource


def build_google_drive_resource() -> GoogleDriveResource:
    with build_resources({"drive": GoogleDriveResource()}) as resources:
        return resources.drive


def test_google_drive_files_list():
    drive = build_google_drive_resource()

    files = drive.files_list(
        corpora="drive",
        drive_id="0AKZ2G1Z8rxooUk9PVA",
        include_items_from_all_drives=True,
        q="'1B40ZL6jjXPMP3FDaHduqwbYmiEbfByNR' in parents",
        supports_all_drives=True,
    )

    assert len(files) > 0


def test_google_drive_files_list_recursive():
    drive = build_google_drive_resource()

    files = drive.files_list_recursive(
        corpora="drive",
        drive_id="0AKZ2G1Z8rxooUk9PVA",
        include_items_from_all_drives=True,
        supports_all_drives=True,
        folder_id="1B40ZL6jjXPMP3FDaHduqwbYmiEbfByNR",
        fields="id,name,mimeType,modifiedTime,size",
    )

    assert len(files) > 0
