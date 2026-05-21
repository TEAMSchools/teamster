# Claude + Cube Connector

This guide walks through connecting your Claude account to the KIPP TEAM &
Family Cube data layer. Once connected, you can ask Claude questions about
attendance, enrollment, grades, and other school metrics directly from
`claude.ai`.

You'll need a `@apps.teamschools.org` Google Workspace account.

## One-time setup

1. Open <https://claude.ai>.
2. In the tools menu (bottom of the chat input), find the **Cube** connector.
3. Click **Connect**. A new browser tab opens.
4. Click **Sign in with Google**.
5. Pick your `@apps.teamschools.org` account.
6. Click **Allow** on the consent screen.
7. The browser returns you to `claude.ai`. The Cube connector now shows
   **Connected**.

That's it. Future sessions reuse this connection silently.

## Asking questions

In a new chat, try:

- "What's network-wide attendance for the last 30 days?"
- "Which schools have the highest enrollment this year?"
- "Show me the absence rate trend over the past three months."

Claude will pick the right Cube tool, run the query under your identity, and
return the answer.

## Troubleshooting

**"Access denied" or empty results** — your account isn't in a `cube-*`
Workspace group with the right permissions. Email the data team to be added.

**"Disconnected" status** — your session has expired. Click **Connect** again
and re-sign-in.

**Wrong account picked at sign-in** — sign out of the other Google account in
that browser tab, then retry the Connect flow.

## Privacy note

Aggregate data (school-level, network-level, grade-level totals) is fine to
share. **Row-level student details should never be copied into emails,
documents, or shared chats** — Claude can show them to you in conversation, but
they're not for redistribution. If you're not sure, ask aggregate-only questions
(use words like "average", "total", "rate").
