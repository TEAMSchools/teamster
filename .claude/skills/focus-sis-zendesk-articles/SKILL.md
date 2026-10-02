---
name: focus-sis-zendesk-articles
description: >-
  Use when drafting or updating a Zendesk help center article for a Focus SIS
  District Report (e.g. HeartBEAT Summary), or when adapting any Focus SIS
  report reference doc/artifact into end-user-facing help content for school
  staff.
---

# Focus SIS Zendesk Help Articles

## Overview

Focus SIS District Reports get built as raw SQL against Focus's schema (see e.g.
the HeartBEAT Summary report, formerly drafted as "Behavior District Report").
Staff who use the report need a separate, plain-language Zendesk article — not
the SQL doc. These are two documents for two audiences; don't conflate them.

## The two-document pattern

1. **Technical/dev reference** — SQL queries, variable definitions,
   Confirmed/Verify status chips, platform-limitation notes. For whoever
   builds/maintains the report in Focus.
2. **End-user help article** — plain language, no SQL, no jargon. What the
   report shows, where to find it in Focus, what each filter does, what the
   output looks like, who to contact. This is what gets pasted into Zendesk.

Before drafting the help article, get these specifics from the user rather than
inventing them — a wrong guess (even a plausible one) misleads the reader and,
for hardcoded filter lists, can silently drop a real value:

- Exact school names (must match `schools.title` spelling exactly)
- Real example category/behavior names
- The exact Focus folder path (e.g. `KIPP` → `Student Experience` → report
  title)
- Actual contact channel (a team email, not a generic placeholder)
- Any platform quirk worth surfacing (e.g. one filter's dropdown not scoped by
  another) — usually yes, since users will hit it and get confused otherwise

## Zendesk's `<style>` gotcha — read before publishing

Zendesk Guide's article source-code editor **strips `<style>` blocks** — they
show as a placeholder while editing but don't render on the live article.
Confirmed against Zendesk's own docs:
[Supported HTML for help center articles](https://support.zendesk.com/hc/en-us/articles/6644509092378-Supported-HTML-for-help-center-articles),
[Editing the source code of help center articles](https://support.zendesk.com/hc/en-us/articles/4408824584602-Editing-the-source-code-of-help-center-articles).
Inline `style="..."` attributes on individual elements ARE supported and are
Zendesk's own documented approach for per-article styling.

Practical effect: a styled artifact built for internal review (external
stylesheet or `<style>` block, CSS custom properties, class-based callouts) is
**not** paste-ready as-is. Build a separate paste-ready fragment:

- No `<title>`, no `<style>` block, no draft/review banner
- No duplicate H1 — the Help Center theme renders the article's **Title** field
  separately; repeating it in the body reads as a redundant heading
- Callouts, table borders/alignment: inline `style="..."` on each element, not
  classes tied to an external sheet
- Paste via the editor's **Source code** (`< >`) button, not the WYSIWYG view
- Verify in a real draft article before wide publish — some Help Center themes
  override inline table styles with their own rules

Starting point: [`zendesk-article-template.html`](zendesk-article-template.html)
— fill in the bracketed placeholders, it's already paste-ready (no `<style>`
block, all inline).

## Content structure for the end-user article

- Standfirst (1-2 sentences): what the report shows, in plain language
- "In this article" anchor nav — plain text links, not a styled box (box styling
  isn't worth inlining for a nav list)
- Where to find it: numbered steps, exact Focus folder path, exact report title.
  Don't describe menu position (e.g. "in the left-hand menu") — it isn't
  consistent across users' Focus setups. Just say "Go to Reports → District
  Reports."
- Choosing your filters: a table (Filter | What it does) covering every
  variable, plus a callout for any real platform quirk
- What the report shows you: one subsection per output table, with a short
  example table using **fictional example names** (e.g. "Alex R.", "Taylor B.")
  explicitly labeled "Names above are examples only, not real students" — never
  real student data in a doc bound for wide internal distribution
- Good to know: recap of quirks/caveats already covered above — no new
  information here
- Get help: the real contact channel

## Common mistakes

- Reusing the technical artifact's SQL-heavy language (table/column names, chip
  statuses) in the help article — end users don't need or want this
- Inventing school/category names instead of asking
- Leaving a placeholder contact (`[fill in: ...]`) in something presented as
  "ready to finalize" — confirm and fill it in before calling it done
- Publishing the styled internal-review artifact's raw HTML directly to Zendesk
  — the `<style>` block silently disappears and the reader gets unstyled,
  unformatted soup
