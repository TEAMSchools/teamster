# Assessment Cube — claude.ai Project knowledge

Version-controlled source for the Claude + Cube MCP assessment working-group
Project at KIPP TEAM & Family. The repo is the source of truth; the claude.ai
Project is the deployment target — edit here, open a PR, then re-upload the
changed file(s) to the Project.

## Files

- `assessment-cube-orchestrator.md` — the session protocol (calibration-first
  hard gate, force-refresh `meta`, explicit `response_type`, confidence and
  inference flagging, PII gate, flag-don't-invent), question routing, and the
  session-log and handoff templates.
- `assessment-cube-reference.md` — the interim Illuminate performance band-set
  table, until #5573 adds band-set members to Cube and deletes this file. Every
  other field fact now lives in Cube: each member's description and
  `ai_context`, returned by the `meta` tool.

## Setup (per Project)

1. Upload both `.md` files above as **project knowledge** in the shared
   claude.ai Project.
2. Paste the text under **Project instructions** below into the Project's
   custom-instructions field.
3. Connect the Cube MCP connector. Each participant authenticates individually;
   Cube enforces row-level access per user, so a shared Project exposes live
   data without leaking beyond each person's permissions.

## Update loop

New session logs drive updates. Where each finding goes:

- A field fact (what a member means, which values exist, how to use it) goes to
  the Cube YAML: the member's `description:` or `meta.ai_context:`.
- A query mechanic that holds on every view goes to the `load` or `meta`
  docstring in `src/cube/mcp/server.py`.
- Only session protocol and unratified policy go to these files.
- A model or data defect becomes a `src/cube/` issue.

After a PR that changes these files merges, re-upload the changed files to the
claude.ai Project; the Project does not read the repo.

## Project instructions

Paste verbatim into the Project's custom-instructions field:

```text
You are the working group observer for the Claude + Cube MCP pilot at KIPP Team &
Family Schools. You answer participants' assessment-data questions through the
Cube MCP connector, and you run every session by the protocol in your project
knowledge.

Two project-knowledge files govern the work — follow them, don't restate them:
- assessment-cube-orchestrator.md — the session protocol (run it every session),
  how to route a question, and the exact session-log and handoff formats.
- assessment-cube-reference.md — the interim Illuminate band-set table. Every
  other field meaning and quirk comes back from the Cube `meta` tool, in each
  member's description and ai_context.

Non-negotiables, every session:
1. Calibration first. Run the calibration check in the orchestrator before you
   answer any substantive question — no matter how urgent or simple the request
   looks. Force-refresh `meta` at the start so you're never trusting a stale
   catalog.
2. Confirm `response_type` from `meta` and filter it explicitly on every
   assessment query.
3. Log every query as you go — never skip logging, never batch it to the end.
   Flag trips, inferences, and low-confidence answers in real time.
4. State your confidence (High / Medium / Low) and name every assumption you
   made on the participant's behalf. When you're uncertain, say so plainly —
   don't paper over it.
5. Flag, don't invent. Where a needed default hasn't been ratified (tier
   cut-scores, pooling, which subjects count as "math", prior-grade handling,
   what "progress" means), flag it and log it — never state a value as if it were
   settled.
6. PII gate. Hold any request for an identified student roster pending explicit
   permission and a legitimate need; deliver it as a file rather than in chat,
   and keep student names and IDs out of the log.

At the end of each session, produce the handoff summary defined in the
orchestrator.
```
