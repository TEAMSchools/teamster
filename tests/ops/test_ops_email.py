from smtplib import SMTPRecipientsRefused

import pytest
from dagster import Failure, InitResourceContext, build_op_context

from teamster.libraries.email.ops import (
    SendPersonalizedEmailOpConfig,
    group_rows_by_email,
    send_personalized_email_op,
)
from teamster.libraries.email.resources import EmailResource

TEMPLATE_PATH = "src/teamster/code_locations/kipptaf/surveys/template.html"

ROWS = [
    {"email": "a@example.org", "survey": "Support Survey", "link": "https://x/a?s=1"},
    {
        "email": "a@example.org",
        "survey": "Manager Survey",
        "link": "https://x/a?m=1&n=2",
    },
    {"email": "b@example.org", "survey": "Support Survey", "link": "https://x/b?s=1"},
]


class FakeEmailResource(EmailResource):
    """Records sends instead of opening an SMTP connection."""

    def setup_for_execution(self, context: InitResourceContext) -> None:
        pass

    def send_message(
        self,
        subject: str,
        from_email: str,
        content_args: tuple,
        bcc_emails: str | None = None,
        to_emails: str | None = None,
        alternative_args: tuple | None = None,
    ) -> None:
        if to_emails in FAILING:
            raise SMTPRecipientsRefused({to_emails: (550, b"rejected")})

        SENT.append(
            {
                "to_emails": to_emails,
                "content_args": content_args,
                "alternative_args": alternative_args,
            }
        )


SENT: list[dict] = []
FAILING: set[str] = set()


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    SENT.clear()
    FAILING.clear()
    monkeypatch.setattr("teamster.libraries.email.ops.time.sleep", lambda _: None)


def _run(rows, **config_overrides):
    send_personalized_email_op(
        context=build_op_context(),
        config=SendPersonalizedEmailOpConfig(
            subject="Survey Reminder",
            text_template="{% for i in items %}{{ i.survey }}: {{ i.link }}\n{% endfor %}",
            html_template_path=TEMPLATE_PATH,
            **config_overrides,
        ),
        email=FakeEmailResource(
            host="localhost", port=25, user="sender@example.org", password="x"
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

    assert [s["to_emails"] for s in SENT] == ["a@example.org", "b@example.org"]

    first_text = SENT[0]["content_args"][0]
    first_html, subtype = SENT[0]["alternative_args"]

    assert subtype == "html"
    assert "Support Survey: https://x/a?s=1" in first_text
    assert "Manager Survey: https://x/a?m=1&n=2" in first_text
    # autoescape turns the query-string & into &amp; inside the href
    assert 'href="https://x/a?m=1&amp;n=2"' in first_html
    assert "https://x/b?s=1" not in first_html


def test_empty_recipients_sends_nothing():
    _run([])

    assert SENT == []


def test_one_failure_keeps_sending_then_fails_the_run():
    FAILING.add("a@example.org")

    with pytest.raises(Failure, match="1 of 2 sends failed"):
        _run(ROWS)

    assert [s["to_emails"] for s in SENT] == ["b@example.org"]


def test_consecutive_failures_stop_the_run_early():
    FAILING.update({"a@example.org", "b@example.org"})
    rows = [*ROWS, {"email": "c@example.org", "survey": "Support Survey", "link": "l"}]

    with pytest.raises(Failure, match="Stopped after 2 failed sends in a row"):
        _run(rows, max_consecutive_failures=2)

    assert SENT == []
