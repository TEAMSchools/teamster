# KIPP NJ | Miami — Design System

A reusable design system for **KIPP Team & Family Schools** in New Jersey and Miami — the brand foundations, components, and product UI kits needed to produce well-branded slides, reports, dashboards, family communications, and web pages.

> **Who this is for.** KIPP New Jersey and KIPP Miami operate free, public charter schools serving roughly 9,000–12,000 students across **Newark, Camden, Paterson (NJ)** and **Miami (FL)**. The uploaded logo is the **KIPP NJ | Miami Data team** lockup; this system is built for the broader network brand with the Data team's analytics product as a first-class surface.

---

## Sources

This system was derived from materials provided by the user:

- **`sources/brand-guidelines-2025-part1.pdf` + `part2.pdf`** — the official KIPP New Jersey / KIPP Miami Brand Guidelines, August 2025 (43 pages). Source of truth for the color palette (Strong Indigo, Confident Red, Vibrant Orange, Fresh Green, Youthful Blue, Crisp White), the Whitney typeface direction, the all-caps heading treatment, the network values ("The Heartbeat"), and the voice & tone "right way / wrong way" examples.
- **`assets/kippnj-miami-logo-white.png`** — the white, four-color Data team logo lockup. Trimmed and re-composited into `assets/logo-white-trimmed.png` and `assets/logo-on-indigo.png`.

No codebase, Figma file, or live site was provided, so the **UI kits and slides are brand-faithful recreations** built from the guidelines, not pixel copies of a shipped product. All school names, rosters, and metrics in them are **illustrative sample data**.

---

## Typography: no webfont by default

The brand typeface is **Whitney** (Hoefler&Co), a licensed commercial font that cannot be redistributed in a design system.

This system previously substituted **Hanken Grotesk** from Google Fonts, loaded via `@import`. That caused inconsistent rendering on Windows, so **as of the 2026 revision nothing is downloaded by default.** Type resolves to the closest humanist sans already installed on each platform:

| Platform | Renders | Why |
|---|---|---|
| Windows | **Segoe UI** | Humanist, tall x-height, open apertures — the nearest system relative of Whitney |
| macOS / iOS | **SF Pro** (`-apple-system`) | Platform default |
| Chromebook / Android | **Roboto** | Heavily used in KIPP classrooms |
| Fallback | **Arial** | Universal |

```
--font-brand: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
```

### What was going wrong

1. **School networks block Google Fonts.** District proxies and content filters routinely block `fonts.googleapis.com`. When the request failed, the page fell back silently — and the old chain listed `'Helvetica Neue'` and `'Helvetica'`, neither of which exists on Windows, *ahead of* any Windows font. Windows machines landed on an unpredictable substitution instead of a chosen face.
2. **Zendesk cannot load webfonts at all.** Help articles allow no `<style>`, `<link>` or `<script>`, so a webfont named in an article never resolves. Every article was already rendering in the fallback.
3. **Unavailable weights were being requested.** Hanken Grotesk is a 300–800 variable font, and designs used 300 and 800. No system font offers those, so Windows faux-bolded or thinned them — the smeared headings and washed-out body text.

### Weights: 400, 600, 700 only

Segoe UI ships Regular, Semibold and Bold; it has no 500 and nothing above 700. All six weight tokens still exist so nothing breaks, but they collapse onto the three safe stops — `--weight-light` → 400, `--weight-medium` → 600, `--weight-extra` → 700. **Do not reintroduce 300, 500 or 800.**

Letter-spacing was also softened (display `-.02em` → `-.01em`), because Segoe UI and Arial are wider than Hanken Grotesk and the old tracking read cramped on Windows. `-webkit-font-smoothing: antialiased` and `text-rendering: optimizeLegibility` were removed from `base.css`: the first thins text on macOS while doing nothing on Windows, which is the exact inconsistency being fixed.

### Opting into a webfont

Fine for marketing pages, slides and standalone artifacts — **never for Zendesk articles.** Add one line to `styles.css`:

```css
@import url('./tokens/fonts-webfont.css');
```

That loads Hanken Grotesk at 400/600/700 and redefines `--font-brand` to prefer it, so every component upgrades at once. If the load fails, the system stack underneath still renders correctly.

**If you license Whitney:** self-host the `.woff2` files under `assets/fonts/`, replace the contents of `tokens/fonts-webfont.css` with your own `@font-face` rules, and keep the family first in `--font-brand`. Self-hosting also sidesteps the blocked-proxy problem entirely, since the files come from your own origin. Ship only 400/600/700. **Please send the Whitney webfont files if you have a license.**

---

## Content fundamentals

How KIPP NJ | Miami writes. The voice is **smart, warm, confident, slightly irreverent, and youthful** — and above all **succinct**.

- **Be brief and direct.** The guide's central rule: cut every word you can. *Right:* "First-year teachers get the support they need." *Wrong:* "First-year, entry-level teachers receive professional development from seasoned, master teachers." Say it plainly.
- **Person & address.** Speak to families and staff as **"you"** and **"our kids," "our team," "we."** It's a community, not an institution talking down to an audience.
- **Casing.** Body copy and headlines in **sentence case**. The signature all-caps is a *typographic treatment* (applied via the heading utilities / components), not a reason to write in capitals. **"TEAM"** and **"TEAMmate"** are intentionally styled — the network's people are its TEAM & Family.
- **Kid-focused & aspirational.** Lead with students and outcomes. Recurring rallying lines come from the **Be The Change Values** (the network's five values, v2 2026): **Kid Focus** (promises to kids are sacred) · **Radical Love** (fierce care, bold belief, high expectations) · **Excellence** (continuous improvement, highest standards) · **TEAM** (Together Everyone Achieves More) · **Fun** (joyful culture, serious mission). (See `assets/be-the-change-values-onepager.pdf` for full definitions and key behaviors.) The mission shorthand is **"to and through college."**
- **No jargon, no edu-speak.** Avoid "leverage," "utilize," "professional development from seasoned master teachers." Prefer everyday words.
- **Emoji:** not used in the brand voice. Don't add them.
- **Numbers:** concrete and proud (95% to college, 9,000 students). The Data team leans on exact figures with tabular alignment.

---

## Visual foundations

- **Color.** Six flat, bold network colors: **Strong Indigo `#001E62`** (the anchor — backgrounds, headlines, primary actions), **Confident Red `#EE3C37`**, **Vibrant Orange `#F9A21A`**, **Fresh Green `#C3D52E`**, **Youthful Blue `#57C0E9`**, **Crisp White**. Accents are used boldly and mostly flat — **no bluish-purple gradients, no soft pastel washes.** Regions pin an interchangeable accent via `data-theme` (Miami = orange, Paterson = red, Newark = blue, Camden = green). Tints/ramps exist for surfaces, chips, and banners but the personality is saturated, not muted.
- **Type.** System humanist sans — Segoe UI on Windows, SF Pro on Apple, Roboto on Chromebooks (see Typography above). Headlines are **bold (700)**; the signature treatment is **semibold ALL CAPS with `.04em` tracking** and a colored **eyebrow/overline** above. Only weights 400/600/700 are used. Body is book-weight sentence case. Data uses **tabular mono** figures.
- **Backgrounds.** Solid brand color fields (especially indigo) and clean white. **Full-bleed accent slides** for section breaks. No repeating patterns, no textures, no gradients. A thin accent bar or top rule is the main decorative device.
- **Photography.** Real, warm, candid photos of students and teachers — and per brand rule, **always square corners and no filters/effects.** That's why `--radius-photo: 0`. (This system ships labeled placeholders; supply real photos in production.)
- **Corners & shape.** Tight and confident: controls `--radius-md: 5px`, cards `--radius-lg: 8px`, pills for tags/badges/avatars. Not soft/rounded; not sharp brutalist.
- **Borders.** 1px subtle dividers; **2px** for emphasis (button outlines, the "pop" card). Accent **top bars** (4–6px) on cards and stat blocks.
- **Elevation.** Subtle **indigo-tinted** drop shadows (`--shadow-sm…xl`). The brand-flavored emphasis device is **`--shadow-pop`**: a hard 6px offset indigo block behind a 2px-outlined card — bold and graphic, not soft.
- **Motion.** Energetic but composed. Quick transitions (`--dur-fast 140ms`, `--dur-base 220ms`) on `--ease-standard`; a gentle **overshoot** (`--ease-spring`) on toggles. **Hover** = subtle lift (`translateY(-2px)`) and/or brightness/color deepen; **press** = slight shrink (`scale(.97)`). Tab/segment indicators slide in. No long floaty fades, no infinite decorative loops. All motion collapses under `prefers-reduced-motion`.
- **Hover/press states.** Buttons brighten + lift on hover, shrink on press; outline/ghost buttons fill with `--indigo-50`. Focus shows a **blue ring** (`--ring`, Youthful Blue).
- **Transparency & blur.** Used sparingly — translucent white chips (`rgba(255,255,255,.1)`) on indigo headers. No glassmorphism / heavy blur.
- **Cards.** White surface, 1px subtle border, small soft shadow, `--radius-lg`. Variants: `pop` (hard indigo offset), `inverse` (indigo fill), `accentBar` (region top bar).
- **Layout.** `--container-max: 1200px`, 4px spacing grid, generous section padding (`--pad-section-y: 80px`). Sticky indigo headers/sidebars.

---

## Iconography

- **No proprietary icon font** is defined in the brand guidelines. Where this system needs UI glyphs it uses a single consistent **line-icon style: ~1.8–2px stroke, round caps/joins, no fill** — drawn inline as SVG inside components (chevrons, arrows, location pin, table trends, etc.).
- **Substitution (flagged):** for component demos and kits that need a broader icon set, this system links **[Lucide](https://lucide.dev)** from CDN — its humanist, rounded-stroke style matches the inline icons above. The `Button` / `IconButton` components accept any icon node, so a Lucide `<i data-lucide="…">`, an inline SVG, or a real `<img>` all work. **If KIPP has a chosen icon set, tell me and I'll swap Lucide for it.**
- **Emoji / unicode as icons:** not part of the brand — avoid.
- **Logo as a mark:** the colon-dot "KIPP:" device is the brand's signature graphic. Use the supplied logo lockups in `assets/`; never retype or recolor the logo.

---

## Index / manifest

**Root**
- `styles.css` — the single entry point consumers link. `@import`-only; reaches all tokens + fonts.
- `README.md` — this guide.
- `COMPONENTS.md` — component → source / types / usage-note map.
- `SKILL.md` — Agent-Skill front-matter so this system can be used in Claude Code.

**`tokens/`** — `fonts.css` (rationale; loads nothing) · `fonts-webfont.css` (optional opt-in) · `colors.css` · `typography.css` · `spacing.css` · `elevation.css` · `motion.css` · `base.css`

**`assets/`** — logo lockups (horizontal + stacked in 4c, indigo, white, white-2c; `logo-white-trimmed.png`, `logo-on-indigo.png`, `kippnj-miami-logo-white.png` Data-team original) · `be-the-change-values-onepager.pdf`

**`_ds_bundle.js`** — prebuilt classic-script bundle of all components; defines `window.KIPPNJMiamiDesignSystem_1916b9`. Used by the `*.card.html` previews and UI-kit pages.

**`sources/`** — the original Brand Guidelines 2025 PDFs and a hi-res logo original. Large; open only when you need to check the source.

**`components/`** (namespace `window.KIPPNJMiamiDesignSystem_1916b9`)
- `actions/` — **Button**, **IconButton**
- `display/` — **Card**, **Badge**, **Tag**, **StatCallout**, **Avatar** / **AvatarGroup**
- `forms/` — **Input**, **Select**, **Checkbox**, **Switch**
- `navigation/` — **Tabs**, **SegmentedControl**

**`guidelines/`** — foundation specimen cards (Colors, Type, Spacing, Brand) shown in the Design System tab.

**`ui_kits/`**
- `website/` — marketing homepage recreation (region switcher, school finder, enrollment modal)
- `data-dashboard/` — the Data team's internal analytics dashboard (KPIs, charts, school comparison)

**`slides/`** — sample presentation templates: title, section divider, stat, quote, content+image (1280×720).

**`zendesk/`** — subsystem for authoring **Zendesk Guide help articles**, where the sanitizer forbids `<style>`, `<script>`, `var()`, flex/grid, `box-shadow`, and `margin` on anything but `<table>`. Article HTML is therefore email-grade: tables for layout, padding for spacing, literal hex values.
- `README.md` — the constraints, the authoring rules, the palette as literals, article structure and voice
- `index.html` — snippet library: every block rendered live with copy-paste source
- `sample-article.html` — a complete article at true help-center width
- `kipp-help-center-theme.css` — optional `.kipp-*` classes to paste into the Guide theme, so authors use class names instead of long inline styles
- For paste-ready article snippets, use the companion **`kipp-zendesk-articles`** skill (ships alongside this one).
