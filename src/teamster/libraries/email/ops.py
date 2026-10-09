import time
from collections import defaultdict
from pathlib import Path

from dagster import Config, Failure, OpExecutionContext, op
from jinja2 import Environment, select_autoescape
from requests import RequestException

from teamster.core.utils.functions import chunk
from teamster.libraries.email.resources import EmailResource, MailSenderResource


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
        html_template_path: Path to a Jinja template for the HTML body.
        messages_per_minute: Send rate cap. Exchange Online's hard limit is 30
            per minute per mailbox, but tenant outbound spam policies can block
            a sender well below that, so the default stays far under it.
        max_recipients: Refuse to send anything if a run has more recipients
            than this, which guards against a bad query emailing far more people
            than intended.
        dry_run: Render every email and log the counts without sending.
        only_send_to: When set, send only to these addresses. Use it to test
            against your own pending surveys before a full run.
        max_consecutive_failures: Stop the run after this many failed sends in
            a row, which means the service or login is down rather than one bad
            address.
    """

    subject: str
    html_template_path: str
    messages_per_minute: int = 8
    max_recipients: int = 2000
    dry_run: bool = False
    only_send_to: list[str] | None = None
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
    email: MailSenderResource,
    recipients: list[dict],
) -> None:
    """Send each recipient one email built from all of their rows.

    `recipients` holds one dict per row with an `email` key. Rows sharing an
    email are passed to the template as `items`, so a person with three pending
    surveys gets one email listing all three.

    Before sending, the op narrows to `only_send_to` when set, and raises
    `Failure` without sending anything if more than `max_recipients` remain.
    A failed send is logged without the address and skipped. The op raises
    `Failure` at the end if any send failed, or right away after
    `max_consecutive_failures` failures in a row.
    """
    html_template = Environment(autoescape=select_autoescape()).from_string(
        Path(config.html_template_path).read_text()
    )

    grouped = group_rows_by_email(recipients)

    if config.only_send_to is not None:
        allowed = {address.lower() for address in config.only_send_to}
        grouped = {k: v for k, v in grouped.items() if k.lower() in allowed}

    if len(grouped) > config.max_recipients:
        raise Failure(
            description=(
                f"{len(grouped)} recipients is over max_recipients "
                f"({config.max_recipients}); nothing was sent"
            )
        )

    delay = 60 / config.messages_per_minute
    context.log.info(
        f"{len(grouped)} emails from {len(recipients)} rows; at "
        f"{config.messages_per_minute}/minute this takes about "
        f"{round(len(grouped) * delay / 60)} minutes"
    )

    if config.dry_run:
        for items in grouped.values():
            html_template.render(items=items)

        context.log.info("Dry run: rendered every email, sent none")
        return

    sent = 0
    failed = 0
    consecutive_failures = 0

    for i, (to_email, items) in enumerate(grouped.items(), start=1):
        try:
            email.send_mail(
                to_email=to_email,
                subject=config.subject,
                html_body=html_template.render(items=items),
            )
        except RequestException as e:
            failed += 1
            consecutive_failures += 1
            status = e.response.status_code if e.response is not None else None
            context.log.warning(
                f"Send {i} of {len(grouped)} failed: {type(e).__name__} {status}"
            )

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

    context.log.info(f"Sent {sent} emails, {failed} failed")

    if failed:
        raise Failure(description=f"{failed} of {len(grouped)} sends failed")
