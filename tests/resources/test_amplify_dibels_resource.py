from bs4 import BeautifulSoup, Tag
from dagster import _check, build_resources

from teamster.code_locations.kipptaf.resources import DIBELS_DATA_SYSTEM_RESOURCE
from teamster.libraries.amplify.dibels.resources import DibelsDataSystemResource

with build_resources(resources={"dds": DIBELS_DATA_SYSTEM_RESOURCE}) as resources:
    DDS: DibelsDataSystemResource = resources.dds


def get_csrf_token(path: str):
    csrf_token_response = DDS._session.request(
        method="POST", url=f"{DDS._base_url}/{path}"
    )

    soup = BeautifulSoup(markup=csrf_token_response.text, features="html.parser")

    csrf_token = _check.inst(
        obj=soup.find(name="meta", attrs={"name": "csrf-token"}), ttype=Tag
    )

    return csrf_token.get("content")


def test_classes_manage_new():
    path = "classes/manage/new"

    post_response = DDS.post(
        path=path,
        data={
            "_token": get_csrf_token(path),
            "name": "spam",
            "teacher": "eggs",
            "grade": "100",
            "type": "0",
            "school": "50621",
            "AcademicYearSchedule": "19646",
            "save": "Save",
        },
    )

    assert post_response.ok


def test_classes_addstudents():
    path = "classes/addstudents"

    post_response = DDS.post(
        path=path,
        params={
            "district": 18095,
            "school": 50621,
            "year": 2024,
            "grade": 100,
            "classroom": 1959352,
            "num_students": 2,
        },
        data={
            "_token": get_csrf_token(path),
            "arrFirstName[0]": "Robert",
            "arrLastName[0]": "Diggs",
            "arrPrimary[0]": "12345",
            "arrSecondary[0]": "98765",
            "arrFirstName[1]": "Dennis",
            "arrLastName[1]": "Coles",
            "arrPrimary[1]": "67890",
            "arrSecondary[1]": "54321",
            "saveForm": "true",
        },
    )

    assert post_response.ok
