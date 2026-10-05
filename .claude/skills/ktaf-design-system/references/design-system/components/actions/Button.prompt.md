Brand action button — bold, all-caps semibold; use for primary calls to action and form submits.

```jsx
<Button variant="accent" size="lg" onClick={apply}>Apply now</Button>
<Button variant="secondary">Learn more</Button>
<Button variant="ghost" size="sm">Cancel</Button>
```

- `variant`: `primary` (indigo, default) · `accent` (region color — orange/blue/red/green via `data-theme`) · `secondary` (indigo outline) · `ghost` (text only)
- `size`: `sm` · `md` (default) · `lg`
- `block` stretches full width; `iconLeft` / `iconRight` accept any node (e.g. a Lucide `<i data-lucide>` or SVG).
- Labels are uppercased by the component — write them in normal case.
