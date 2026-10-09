import time
from email.message import EmailMessage
from smtplib import SMTP

from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr
from requests import HTTPError, RequestException, Response, Session
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


class EmailResource(ConfigurableResource):
    host: str
    port: int
    user: str
    password: str
    chunk_size: int = 1
    timeout: int = 30

    _server: SMTP = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext):
        self._log = check.not_none(value=context.log)

        self._server = SMTP(host=self.host, port=self.port, timeout=self.timeout)

        # SMTP handshake
        self._server.ehlo()
        self._server.starttls()

        self._server.login(user=self.user, password=self.password)

    def send_message(
        self,
        subject: str,
        from_email: str,
        content_args: tuple,
        bcc_emails: str | None = None,
        to_emails: str | None = None,
        alternative_args: tuple | None = None,
    ):
        if to_emails is None:
            to_emails = from_email

        msg = EmailMessage()

        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_emails
        msg.set_content(*content_args)

        if bcc_emails is not None:
            msg["Bcc"] = bcc_emails

        if alternative_args is not None:
            msg.add_alternative(*alternative_args)

        try:
            self._server.send_message(msg=msg)
            self._log.info(f"Email sent to {to_emails} {bcc_emails}")
        except Exception as e:
            self._log.error(msg=e)


class TransientHTTPError(HTTPError):
    """A response worth retrying: throttled (429) or a 5xx."""


class ZapierWebhookError(RequestException):
    """A failed Zapier webhook call, with the secret webhook URL kept out."""


class MailSenderResource(ConfigurableResource):
    """Base for resources that send one HTML email per `send_mail` call.

    Provides an HTTP session and a `_request` that retries throttling, 5xx,
    connection errors, and timeouts. Error messages never include the request
    URL, because some subclasses keep a secret in it.
    """

    timeout: int = 30

    _session: Session = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._session = Session()

    @retry(
        retry=retry_if_exception_type(
            (TransientHTTPError, RequestsConnectionError, Timeout)
        ),
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=2, max=60),
        reraise=True,
    )
    def _request(self, method: str, url: str, **kwargs) -> Response:
        response = self._session.request(
            method=method, url=url, timeout=self.timeout, **kwargs
        )

        if response.status_code == 429 or response.status_code >= 500:
            raise TransientHTTPError(
                f"{response.status_code} response", response=response
            )

        if response.status_code >= 400:
            raise HTTPError(f"{response.status_code} response", response=response)

        return response

    def send_mail(self, to_email: str, subject: str, html_body: str) -> None:
        raise NotImplementedError


class GraphEmailResource(MailSenderResource):
    """Send email as one mailbox through Microsoft Graph, with app-only auth.

    Signs in with the OAuth client credentials flow. The Entra app needs the
    Application `Mail.Send` permission, and Exchange should scope that
    permission to `sender` only; unscoped, the app can send as any mailbox.

    https://learn.microsoft.com/en-us/graph/api/user-sendmail

    Attributes:
        tenant_id: Entra tenant ID.
        client_id: Entra app (client) ID.
        client_secret: Entra app client secret.
        sender: Mailbox address the email is sent from.
    """

    tenant_id: str
    client_id: str
    client_secret: str
    sender: str

    _token: str = PrivateAttr(default="")
    _token_expires_at: float = PrivateAttr(default=0.0)

    def _get_token(self) -> str:
        # refresh 5 minutes early so a long send loop never uses an expired token
        if time.monotonic() < self._token_expires_at - 300:
            return self._token

        response = self._request(
            method="POST",
            url=f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        payload = response.json()

        self._token = payload["access_token"]
        self._token_expires_at = time.monotonic() + payload["expires_in"]

        return self._token

    def send_mail(self, to_email: str, subject: str, html_body: str) -> None:
        """Send one HTML email from `sender` to `to_email`.

        Raises `requests.HTTPError` when Graph rejects the message, after
        retrying throttling and server errors.
        """
        self._request(
            method="POST",
            url=f"https://graph.microsoft.com/v1.0/users/{self.sender}/sendMail",
            headers={"Authorization": f"Bearer {self._get_token()}"},
            json={
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": html_body},
                    "toRecipients": [{"emailAddress": {"address": to_email}}],
                },
                "saveToSentItems": False,
            },
        )


class ZapierWebhookEmailResource(MailSenderResource):
    """Hand each email to a Zap that catches a webhook and sends it.

    Posts `email`, `subject`, and `html` to a Webhooks by Zapier Catch Hook.
    The Zap's email action decides the sender and holds the mail connection.
    A success response means Zapier accepted the request, not that the email
    was delivered; delivery errors show up in the Zap's task history.

    Attributes:
        webhook_url: The Catch Hook URL. Treat it as a secret: anyone holding
            it can send email through the Zap.
    """

    webhook_url: str

    def send_mail(self, to_email: str, subject: str, html_body: str) -> None:
        """Post one email to the Zap.

        Raises `ZapierWebhookError`, without the URL or the original message,
        when the call fails after retries.
        """
        error: RequestException | None = None

        try:
            self._request(
                method="POST",
                url=self.webhook_url,
                json={"email": to_email, "subject": subject, "html": html_body},
            )
        except RequestException as e:
            error = e

        # raised outside the except block so the original exception, whose
        # message can contain the webhook URL, is not attached as context
        if error is not None:
            raise ZapierWebhookError(
                f"{type(error).__name__} {getattr(error.response, 'status_code', None)}",
                response=error.response,
            )
