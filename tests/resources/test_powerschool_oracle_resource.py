from teamster.libraries.dlt.powerschool.resources import OracleResource


def test_connection_url_quotes_password():
    resource = OracleResource(
        user="psnavigator",
        password="p@ss/wo:rd",
        host="localhost",
        port="1521",
        service_name="PSPRODDB",
    )

    assert resource.connection_url() == (
        "oracle+oracledb://psnavigator:p%40ss%2Fwo%3Ard@localhost:1521"
        "/?service_name=PSPRODDB"
    )
