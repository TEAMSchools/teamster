# Zendesk Help Article HTML — KIPP NJ | Miami

A constrained subsystem of the KIPP NJ | Miami design system for authoring
**help center articles in Zendesk Guide**. Everything here is built to survive
Zendesk's HTML sanitizer with **Display Unsafe Content turned OFF** (the
default, and the only safe assumption).

Source of truth:
[Supported HTML for help center articles](https://support.zendesk.com/hc/en-us/articles/6644509092378-Supported-HTML-for-help-center-articles)
(Zendesk, retrieved Aug 2026).

---

## The constraints that shape every decision

Zendesk limits the HTML you can use in articles and content blocks to keep the
help center secure. In practice this makes article HTML **email-grade**, not
web-grade.

### What you cannot use

| Not available                                      | Consequence                                                                                                                                     |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `<style>` blocks, `<link>`, `<script>`             | No stylesheet of your own. Every rule is an inline `style="…"` attribute, or a class your Guide **theme** already defines.                      |
| CSS custom properties (`--x`, `var()`)             | Not on the allowed inline-style list. **Write literal hex values** in article HTML — you cannot reference the design system's tokens.           |
| `margin` on most elements                          | Allowed **only on `<table>`** (`margin`, `margin-top/right/bottom/left`). Vertical rhythm has to come from tables or padding.                   |
| `box-shadow`, `opacity`, `transform`, `transition` | No elevation system, no motion. Use `border` and flat fills.                                                                                    |
| `position`, `float`                                | `float` is allowed on `<figure>` only. No overlays, no sticky elements.                                                                         |
| Flexbox & grid                                     | `display` is allowed, but `gap`, `flex-direction`, `align-items`, `justify-content`, `grid-template-*` are **not**. Flex and grid are unusable. |
| `<button>`, `<input>`, `<form>`, `<svg>`           | Not supported elements. Buttons are styled `<a>` tags. Icons must be `<img>` or Unicode.                                                        |

### What you do get

- **Structure**: `div`, `span`, `section`, `article`, `aside`, `header`,
  `footer`, `nav`, `figure`, `figcaption`, `details`, `summary`, `h1`–`h6`, `p`,
  `hr`, `br`, `blockquote`, `pre`, `ul`/`ol`/`li`, `dl`/`dt`/`dd`, full `table`
  family.
- **Inline**: `a`, `strong`, `em`, `code`, `kbd`, `samp`, `var`, `mark`, `abbr`,
  `sub`, `sup`, `del`, `ins`, `s`, `small`, `q`, `cite`, `time`, `data`.
- **Media**: `img`, `video`, `audio`, `source`, `track`, and `iframe` — but
  iframes only from an allowlist of domains: YouTube / youtube-nocookie, Vimeo,
  Loom, Wistia, Vidyard, Brightcove, JW Player, Microsoft Stream, microsoft.com.
- **Global attributes on everything**: `aria-*`, `class`, `data-*`, `dir`, `id`,
  `lang`, `tabindex`, `title`.
- **Global inline styles**: `background`, `background-color`,
  `background-image`, all `border-*`, `border-radius`, `border-collapse`,
  `border-spacing`, `box-sizing`, `color`, `display`, all `font-*`, `height`,
  `letter-spacing`, `line-height`, `max-height`, `max-width`, `min-height`,
  `min-width`, `outline`, all `padding-*`, `text-align`, all
  `text-decoration-*`, `text-indent`, `text-transform`, `vertical-align`,
  `white-space`, `width`, `word-spacing`, `aspect-ratio`.
- **Element-specific styles**: `margin*` on `table` · `float` on `figure` ·
  `list-style*` on `ul`, `ol`, `li`.

### Two gotchas that bite

1. **Empty elements get removed.** Zendesk strips most empty containers such as
   `i` or `span`, so the Font Awesome `<i class="fa-…"></i>` trick does not
   survive — and neither does a spacer `<td>` used as a coloured rule. Empty
   `<p>` tags are kept but filled with `&nbsp;`.
1. **Sanitizing is invisible.** Unsafe HTML is not stripped from the stored
   article — it is just left out of the response sent to the browser, so the
   editor looks fine and the published page does not. Always check the published
   article, not the editor preview.
1. **A stripped declaration is worse than a missing one.** When Zendesk drops
   `margin:0`, the element does not fall back to "no margin" — it falls back to
   the _browser default_, which is usually 1em. This is why the div-not-p rule
   above matters more than it looks.

---

## The rules we author by

1. **Every block-level component is a `<table>`.** It is the only element that
   takes `margin`, so it is the only way to control the space between blocks.
   Use `width:100%`, `border-collapse:collapse`, `cellpadding="0"`,
   `cellspacing="0"`, and put padding on the `<td>`.
1. **Spacing lives on `td` padding**, on the 4px grid: 8 / 12 / 16 / 20 / 24
   / 32.
1. **Inside a `<td>`, use `<div>` — never `<p>`.** This is the rule people get
   wrong. `<p>`, `<h2>`, `<ul>`, `<ol>`, `<pre>` and `<figure>` all carry a
   default browser margin, and `margin:0` on them is _stripped_, so the margin
   returns on the published page and the block inflates. `<div>` has no default
   margin, so it renders identically in your editor and in production.
   Consequences:
   - Callout labels and body copy are `<div>`s.
   - Code blocks are `<div style="white-space:pre-wrap">` wrapping a `<code>`,
     not `<pre>`.
   - Screenshots are a `<div>` + `<img>` + caption `<div>`, not
     `<figure>`/`<figcaption>` — `<figure>`'s default `1em 40px` margin cannot
     be zeroed and would indent the image 40px against every other block.
   - `<ul>`/`<ol>` stay, because a procedure needs to be a real list: set
     `padding-left` only, space items with `padding-bottom` on the `<li>`, and
     let the list's default vertical margin sit inside the `td`.
   - `<h2>` stays for structure and anchors. Do not fight its default margin; it
     is reasonable spacing.
1. **Accent bars are `border-left`, not a spacer cell.** A 4px `<td>` holding
   only a background colour is an empty element, and Zendesk deletes those. Put
   `border-left:4px solid <accent>` on the content cell instead.
1. **Literal hex, every time.** Copy the values from the palette below. No
   `var()`.
1. **Flat, square, bordered.** No shadows exist, and the brand is flat anyway: a
   1px border plus a tinted fill is the card. Radius stays at `0` or `3px`;
   photos stay square.
1. **Headings are the brand treatment** — semibold/bold, uppercase,
   `letter-spacing:.04em` — but the _words_ are sentence case.
1. **Set `font-family` inline on the outermost element of each block** and let
   children inherit. Guide themes vary; do not assume yours loads the brand
   face.
1. **Test published, on mobile.** Tables do not reflow. Keep data tables to 4
   columns or fewer.

---

## Palette for article HTML

Paste these literals. They match `tokens/colors.css`.

| Role                              | Hex                                                                |
| --------------------------------- | ------------------------------------------------------------------ |
| Strong Indigo (headings, primary) | `#001E62`                                                          |
| Body text                         | `#2a3340`                                                          |
| Muted text                        | `#5a6675`                                                          |
| Hairline border                   | `#d6dde7`                                                          |
| Page tint / code background       | `#f4f6f9`                                                          |
| Indigo tint / border              | `#eef3fc` / `#b9caf0`                                              |
| Note — blue                       | fill `#f0fafe` · border `#bce5f7` · bar `#57C0E9` · text `#1f7fb0` |
| Tip — green                       | fill `#f9fbe9` · border `#e4eea0` · bar `#C3D52E` · text `#7e8c12` |
| Warning — orange                  | fill `#fff6e8` · border `#fcd99b` · bar `#F9A21A` · text `#b96b00` |
| Critical — red                    | fill `#fef0ef` · border `#f7b9b6` · bar `#EE3C37` · text `#b81f1b` |

Font stacks:

```text
'Hanken Grotesk', Whitney, 'Helvetica Neue', Helvetica, Arial, sans-serif
'JetBrains Mono', Consolas, Monaco, 'Courier New', monospace
```

---

## Article structure

A KIPP help article follows this order:

1. **`<h1>`** — Zendesk renders the article title itself. **Do not repeat it in
   the body.** Start body headings at `<h2>`.
1. **Summary paragraph** — one or two sentences on what the reader will
   accomplish.
1. **Audience / prerequisites panel** — who this is for, what they need first.
1. **In this article** — a table of contents for anything over three sections.
   Link to `#anchors` set with `id` on the `<h2>`.
1. **Body** — `<h2>` sections, numbered steps, callouts, screenshots.
1. **Related articles** — closing list of links.

Heading levels never skip. Anchor ids are lowercase and hyphenated.

---

## Voice

The parent brand voice applies (see the root `readme.md`), tightened for
instructions:

- **Second person, imperative.** "Open the Settings tab," not "The user should
  open…"
- **Sentence case in the words**, uppercase only as a typographic treatment on
  labels.
- **One action per numbered step.** If a step has an "and" in it, it is two
  steps.
- **Name UI elements exactly** as they appear, in `<strong>`: click **Save
  changes**.
- **Keyboard keys** go in `<kbd>`. **Literal values, paths and field entries**
  go in `<code>`.
- **Say what happens after.** End a procedure with the confirmation the reader
  should see.
- No emoji. No "simply," "just," or "easy" — if it were easy they would not be
  reading this.

---

## Files

| File                         | What it is                                                                                                                                       |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `index.html`                 | **Snippet library.** Every component rendered live with its copy-paste source. Start here.                                                       |
| `sample-article.html`        | A complete article composed from the snippets, at true help-center width.                                                                        |
| `kipp-help-center-theme.css` | Optional. Paste into your Guide theme's stylesheet to get `.kipp-*` classes, so authors can use short class names instead of long inline styles. |

### If you can edit the Guide theme

Adding `kipp-help-center-theme.css` to the theme is strictly better: `class` is
an allowed global attribute, so authors write
`<div class="kipp-callout kipp-callout--warning">` instead of 300 characters of
inline style. The inline snippets remain the fallback for any instance where
theme access is not available — and they keep working if the theme changes.
