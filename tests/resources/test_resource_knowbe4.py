import requests


def test_foo():
    session = requests.Session()

    session.headers["Authorization"] = "Bearer ..."

    response = session.get(url="https://us.api.knowbe4.com/v1/users")

    response
