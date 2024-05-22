from dagster import AssetExecutionContext, asset, materialize
from playwright.sync_api import sync_playwright
from requests import Session

from teamster.amplify.dibels.resources import DibelsDataSystemResource


@asset
def foo(context: AssetExecutionContext, dds: DibelsDataSystemResource):
    dds.report(
        report="DataFarming",
        scope="District",
        district=109,
        grade="_ALL_",
        start_year=2023,
        end_year=2023,
        assessment=15030,
        assessment_period="_ALL_",
        student_filter="none",
        delimiter=0,
        growth_measure=16240,
    )

    """
    Fields[]: 
    Fields[]: 1
    Fields[]: 2
    Fields[]: 3
    Fields[]: 4
    Fields[]: 5
    Fields[]: 21
    Fields[]: 22
    Fields[]: 23
    Fields[]: 25
    Fields[]: 26
    Fields[]: 27
    Fields[]: 41
    Fields[]: 43
    Fields[]: 44
    Fields[]: 45
    Fields[]: 47
    Fields[]: 48
    Fields[]: 49
    Fields[]: 51
    Fields[]: 50
    Fields[]: 61
    Fields[]: 62
    """


def test_foo():
    result = materialize(
        assets=[foo],
        resources={"dds": DibelsDataSystemResource(username="", password="")},
    )

    assert result.success


def test_bar():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        page = browser.new_page()

        page.goto(url="https://dibels.amplify.com")
        name_element = page.locator(selector="#name")
        password_element = page.locator(selector="#password")

        name_element.fill(value="")
        password_element.fill(value="")

        page.click(selector="#login > div > div:nth-child(3) > div > input")

        page.goto(
            url="https://dibels.amplify.com/reports/report.php?"
            + "&".join(
                [
                    "report=DataFarming",
                    "Scope=District",
                    "district=109",
                    "Grade=_ALL_",
                    "StartYear=2023",
                    "EndYear=2023",
                    "Assessment=15030",
                    "AssessmentPeriod=_ALL_",
                    "StudentFilter=any",
                    "Fields%5B%5D=",
                    "Fields%5B%5D=1",
                    "Fields%5B%5D=2",
                    "Fields%5B%5D=3",
                    "Fields%5B%5D=4",
                    "Fields%5B%5D=5",
                    "Fields%5B%5D=21",
                    "Fields%5B%5D=22",
                    "Fields%5B%5D=23",
                    "Fields%5B%5D=25",
                    "Fields%5B%5D=26",
                    "Fields%5B%5D=27",
                    "Fields%5B%5D=41",
                    "Fields%5B%5D=43",
                    "Fields%5B%5D=44",
                    "Fields%5B%5D=45",
                    "Fields%5B%5D=47",
                    "Fields%5B%5D=48",
                    "Fields%5B%5D=49",
                    "Fields%5B%5D=51",
                    "Fields%5B%5D=50",
                    "Fields%5B%5D=61",
                    "Fields%5B%5D=62",
                    "Delimiter=0",
                    "GrowthMeasure=16240",
                ]
            )
        )

        csv_link_element = page.locator(selector=".csv-link")

        href = csv_link_element.get_attribute(name="href")
        cookies = page.context.cookies()

        browser.close()

    session = Session()
    for c in cookies:
        session.cookies.set(
            name=c["name"],
            value=c["value"],
            domain=c["domain"],
            path=c["path"],
            expires=c["expires"],
            secure=c["secure"],
        )

    response = session.get(href)
