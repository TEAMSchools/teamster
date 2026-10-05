Signature big-number metric block with tabular figures; use across reports, dashboards and slides to headline outcomes.

```jsx
<StatCallout value="95.2%" label="College enrollment" sub="Class of 2025" />
<StatCallout value="9,000" label="Students" size="lg" tone="accent" />
<StatCallout value="61.2%" label="FRL eligible" trend={{ dir: 'up', text: '+3.1 pts' }} />
```

- `size`: `sm | md | lg`; `tone`: `default | accent | inverse` (inverse for indigo backgrounds).
- `trend` = `{ dir: 'up' | 'down', text }` renders a colored arrow + delta.
