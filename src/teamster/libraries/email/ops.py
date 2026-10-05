import time
from collections import defaultdict
from pathlib import Path
from smtplib import SMTPException

from dagster import Config, Failure, OpExecutionContext, op
from jinja2 import Environment, Template, select_autoescape

from teamster.core.utils.functions import chunk
from teamster.libraries.email.resources import EmailResource


class SendEmailOpConfig(Config):
    subject: str
    text_body: str
    template_path: str | None = None


@op
def send_email_op(
    context: OpExecutionContext,
    config: SendEmailOpConfig,
    email: EmailResource,
    recipients,
):
    if config.template_path:
        alternative_args = (Path(config.template_path).read_text(), "html")
    else:
        alternative_args = None

    for i, batch in enumerate(chunk(obj=recipients, size=email.chunk_size)):
        context.log.info(f"Processing batch {i} ({len(batch)} recipients)")

        email.send_message(
            subject=config.subject,
            from_email=email.user,
            bcc_emails=",".join([r["email"] for r in batch]),
            content_args=(config.text_body,),
            alternative_args=alternative_args,
        )


class SendPersonalizedEmailOpConfig(Config):
    """Config for `send_personalized_email_op`.

    Attributes:
        subject: Subject line for every email.
        text_template: Jinja template for the plain-text body.
        html_template_path: Path to a Jinja template for the HTML body.
        messages_per_minute: Send rate cap. Exchange Online allows 30 messages
            per minute per mailbox, so the default leaves headroom.
        max_consecutive_failures: Stop the run after this many failed sends in
            a row, which means the server or login is down rather than one bad
            address.
    """

    subject: str
    text_template: str
    html_template_path: str
    messages_per_minute: int = 25
    max_consecutive_failures: int = 5


def group_rows_by_email(rows: list[dict]) -> dict[str, list[dict]]:
    """Group row dicts that each carry an `email` key into one list per email."""
    grouped = defaultdict[str, list[dict]](list)

    for row in rows:
        grouped[row["email"]].append(row)

    return dict(grouped)


@op
def send_personalized_email_op(
    context: OpExecutionContext,
    config: SendPersonalizedEmailOpConfig,
    email: EmailResource,
    recipients: list[dict],
) -> None:
    """Send each recipient one email built from all of their rows.

    `recipients` holds one dict per row with an `email` key. Rows sharing an
    email are passed to both templates as `items`, so a person with three
    pending surveys gets one email listing all three.

    A failed send is logged and skipped. The op raises `Failure` at the end if
    any send failed, or right away after `max_consecutive_failures` failures in
    a row.
    """
    html_template = Environment(autoescape=select_autoescape()).from_string(
        Path(config.html_template_path).read_text()
    )
    text_template = Template(config.text_template)

    grouped = group_rows_by_email(recipients)
    delay = 60 / config.messages_per_minute

    context.log.info(f"Sending {len(grouped)} emails from {len(recipients)} rows")

    sent = 0
    failed: list[str] = []
    consecutive_failures = 0

    for to_email, items in grouped.items():
        try:
            email.send_message(
                subject=config.subject,
                from_email=email.user,
                to_emails=to_email,
                content_args=(text_template.render(items=items),),
                alternative_args=(html_template.render(items=items), "html"),
            )
        except SMTPException as e:
            failed.append(to_email)
            consecutive_failures += 1
            context.log.warning(f"Send failed for {to_email}: {e}")

            if consecutive_failures >= config.max_consecutive_failures:
                raise Failure(
                    description=(
                        f"Stopped after {consecutive_failures} failed sends in a "
                        f"row ({sent} sent, {len(grouped) - sent} not sent)"
                    )
                ) from e
        else:
            sent += 1
            consecutive_failures = 0

        time.sleep(delay)

    context.log.info(f"Sent {sent} emails, {len(failed)} failed")

    if failed:
        raise Failure(description=f"{len(failed)} of {len(grouped)} sends failed")
