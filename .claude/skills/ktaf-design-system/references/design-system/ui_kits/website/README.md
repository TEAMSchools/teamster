# Marketing Website — UI kit

A recreation of a KIPP NJ | Miami public-facing marketing site (in the spirit of kippnj.org), built entirely from this design system's tokens and components.

## Run
Open `index.html`. It loads `styles.css` + the compiled `_ds_bundle.js`, then mounts the React surfaces below.

## What it demonstrates
- **Region switcher** in the header — Newark / Camden / Paterson / Miami. Switching sets `data-theme` on `<body>`, which swaps the interchangeable brand accent (blue / green / red / orange) across the whole page, and changes the school list.
- **Enrollment flow** — "Enroll now" / "Apply" buttons open `ApplyModal`, a working multi-field form with a success state.
- **School finder** — filterable card grid (All / Elementary / Middle / High).

## Surfaces
- `SiteHeader.jsx` — indigo sticky nav, logo, region dropdown, enroll CTA
- `Hero.jsx` — headline, dual CTAs, photo with floating stat chip
- `StatBand.jsx` — four big-number `StatCallout`s
- `SchoolFinder.jsx` — tag-filtered grid of school `Card`s
- `ValueProps.jsx` — "The Heartbeat" network values
- `CTABand.jsx` — full-bleed accent enrollment band
- `SiteFooter.jsx` — indigo footer, link columns
- `ApplyModal.jsx` — enrollment form + confirmation
- `PhotoFrame.jsx` — kit-local placeholder standing in for brand photography (square corners, no filter, per brand rule). **Swap for real `<img>` in production.**

## Notes
- School names and per-region rosters are **illustrative**, not an authoritative list of KIPP schools.
- Photography is represented by labeled placeholders — no licensed photos ship with this system.
