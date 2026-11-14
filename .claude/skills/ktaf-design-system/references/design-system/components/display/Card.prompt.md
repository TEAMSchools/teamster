Base surface container for grouping content; use for stat blocks, school cards, panels.

```jsx
<Card elevation="md">…</Card>
<Card pop>Hard-offset indigo emphasis</Card>
<Card inverse accentBar>White text on indigo</Card>
<Card interactive onClick={open}>Lifts on hover</Card>
```

- `elevation`: `flat | sm | md | lg`; `pop` overrides with the brand hard-offset block.
- `inverse` fills indigo, `accentBar` adds a region-colored top bar, `interactive` adds hover lift.
- `pad` (default true) toggles built-in padding — set false to bleed images to the edge.
