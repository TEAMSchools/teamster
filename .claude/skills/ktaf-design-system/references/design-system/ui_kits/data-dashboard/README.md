# Data Dashboard — UI kit

An internal analytics dashboard for the KIPP NJ | Miami **Data team** — the most on-brand product surface in this system. Built entirely from the design tokens and components.

## Run
Open `index.html`. Loads `styles.css` + `_ds_bundle.js`, then mounts the React surfaces.

## What it demonstrates
- **Sidebar navigation** (Overview / Academics / Attendance / Enrollment / Staff) on Strong Indigo.
- **School selector** + **time-range** segmented control + **export** in the topbar.
- **KPI row** of `StatCallout`s with trend deltas.
- **Charts** — grouped bar (proficiency vs district), conic donut (enrollment mix) — using the categorical `--viz-*` palette.
- **School comparison table** with region `Badge`s and trend arrows, tabular mono figures.

## Surfaces
- `DashSidebar.jsx` · `DashTopbar.jsx` · `DashBody.jsx` (+ `KpiRow`) · `Charts.jsx` (`BarChart`, `Donut`) · `DataTable.jsx`

## Notes
- All figures, school names and rosters are **illustrative sample data**, not real KIPP results.
- Charts are lightweight CSS/SVG recreations for visual fidelity, not a charting library.
