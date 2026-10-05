from pathlib import Path
from types import SimpleNamespace

import pytest
from dagster import Failure, InitResourceContext, build_op_context
from requests import HTTPError, Response
from tenacity import wait_none

from teamster.libraries.email.ops import (
    SendPersonalizedEmailOpConfig,
    group_rows_by_email,
    send_personalized_email_op,
)
from teamster.libraries.email.resources import GraphEmailResource

TEMPLATE_PATH = (
    Path(__file__).parents[2]
    / "src/teamster/code_locations/kipptaf/surveys/template.html"
)

ROWS = [
    {"email": "a@example.org", "survey": "Support Survey", "link": "https://x/a?s=1"},
    {
        "email": "a@example.org",
        "survey": "Manager Survey",
        "link": "https://x/a?m=1&n=2",
    },
    {"email": "b@example.org", "survey": "Support Survey", "link": "https://x/b?s=1"},
]

SENT: list[dict] = []
FAILING: set[str] = set()


def _response(status_code: int, payload: dict | None = None) -> Response:
    response = Response()
    response.status_code = status_code
    response.url = "https://graph.example"
    response._content = (str(payload or {}).replace("'", '"')).encode()

    return response


class FakeGraphEmailResource(GraphEmailResource):
    """Records sends instead of calling Graph."""

    def setup_for_execution(self, context: InitResourceContext) -> None:
        pass

    def send_mail(self, to_email: str, subject: str, html_body: str) -> None:
        if to_email in FAILING:
            raise HTTPError("400 Bad Request", response=_response(400))

        SENT.append({"to_email": to_email, "subject": subject, "html": html_body})


def _graph_resource() -> GraphEmailResource:
    return GraphEmailResource(
        tenant_id="tenant",
        client_id="client",
        client_secret="secret",
        sender="sender@example.org",
    )


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    SENT.clear()
    FAILING.clear()
    monkeypatch.setattr("teamster.libraries.email.ops.time.sleep", lambda _: None)
    monkeypatch.setattr(GraphEmailResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]


def _run(rows, context=None, **config_overrides):
    send_personalized_email_op(
        context=context or build_op_context(),
        config=SendPersonalizedEmailOpConfig(
            subject="Survey Reminder",
            html_template_path=str(TEMPLATE_PATH),
            **config_overrides,
        ),
        email=FakeGraphEmailResource(
            tenant_id="t", client_id="c", client_secret="s", sender="s@example.org"
        ),
        recipients=rows,
    )


def test_group_rows_by_email():
    grouped = group_rows_by_email(ROWS)

    assert list(grouped) == ["a@example.org", "b@example.org"]
    assert [r["survey"] for r in grouped["a@example.org"]] == [
        "Support Survey",
        "Manager Survey",
    ]


def test_sends_one_email_per_person_with_their_links():
    _run(ROWS)

    assert [s["to_email"] for s in SENT] == ["a@example.org", "b@example.org"]

    first_html = SENT[0]["html"]

    assert "https://x/a?s=1" in first_html
    # autoescape turns the query-string & into &amp; inside the href
    assert 'href="https://x/a?m=1&amp;n=2"' in first_html
    assert "https://x/b?s=1" not in first_html


def test_empty_recipients_sends_nothing():
    _run([])

    assert SENT == []


def test_one_failure_keeps_sending_then_fails_the_run(caplog):
    FAILING.add("a@example.org")

    with pytest.raises(Failure, match="1 of 2 sends failed"):
        _run(ROWS)

    assert [s["to_email"] for s in SENT] == ["b@example.org"]
    assert "a@example.org" not in caplog.text


def test_consecutive_failures_stop_the_run_early():
    FAILING.update({"a@example.org", "b@example.org"})
    rows = [*ROWS, {"email": "c@example.org", "survey": "Support Survey", "link": "l"}]

    with pytest.raises(Failure, match="Stopped after 2 failed sends in a row"):
        _run(rows, max_consecutive_failures=2)

    assert SENT == []


def test_graph_send_mail_fetches_token_once_and_posts_message():
    calls = []

    def fake_request(method, url, timeout, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        if "oauth2" in url:
            return _response(200, {"access_token": "tok", "expires_in": 3600})
        return _response(202)

    resource = _graph_resource()
    resource._session = SimpleNamespace(request=fake_request)  # type: ignore[assignment]

    resource.send_mail(to_email="a@example.org", subject="Hi", html_body="<p>x</p>")
    resource.send_mail(to_email="b@example.org", subject="Hi", html_body="<p>y</p>")

    token_calls = [c for c in calls if "oauth2" in c["url"]]
    send_calls = [c for c in calls if "sendMail" in c["url"]]

    assert len(token_calls) == 1
    assert token_calls[0]["data"]["grant_type"] == "client_credentials"
    assert len(send_calls) == 2
    assert send_calls[0]["url"].endswith("/users/sender@example.org/sendMail")
    assert send_calls[0]["headers"] == {"Authorization": "Bearer tok"}
    assert send_calls[0]["json"]["message"]["toRecipients"] == [
        {"emailAddress": {"address": "a@example.org"}}
    ]
    assert send_calls[0]["json"]["message"]["body"]["contentType"] == "HTML"


def test_graph_token_refreshes_when_near_expiry():
    tokens = iter(["first", "second"])

    def fake_request(method, url, timeout, **kwargs):
        if "oauth2" in url:
            # expires inside the 5-minute refresh margin, so the next call refetches
            return _response(200, {"access_token": next(tokens), "expires_in": 60})
        return _response(202)

    resource = _graph_resource()
    resource._session = SimpleNamespace(request=fake_request)  # type: ignore[assignment]

    assert resource._get_token() == "first"
    assert resource._get_token() == "second"


def test_graph_retries_throttling_then_succeeds():
    statuses = iter([429, 202])
    send_attempts = []

    def fake_request(method, url, timeout, **kwargs):
        if "oauth2" in url:
            return _response(200, {"access_token": "tok", "expires_in": 3600})
        send_attempts.append(url)
        return _response(next(statuses))

    resource = _graph_resource()
    resource._session = SimpleNamespace(request=fake_request)  # type: ignore[assignment]

    resource.send_mail(to_email="a@example.org", subject="Hi", html_body="<p>x</p>")

    assert len(send_attempts) == 2


def test_graph_does_not_retry_client_errors():
    send_attempts = []

    def fake_request(method, url, timeout, **kwargs):
        if "oauth2" in url:
            return _response(200, {"access_token": "tok", "expires_in": 3600})
        send_attempts.append(url)
        return _response(400)

    resource = _graph_resource()
    resource._session = SimpleNamespace(request=fake_request)  # type: ignore[assignment]

    with pytest.raises(HTTPError):
        resource.send_mail(to_email="bad", subject="Hi", html_body="<p>x</p>")

    assert len(send_attempts) == 1
