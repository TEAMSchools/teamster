Compact 2–4 option switch for tight spaces; use for chart-range or view toggles in toolbars.

```jsx
const [range, setRange] = React.useState('ytd');
<SegmentedControl value={range} onChange={setRange}
  options={[{value:'mo',label:'Month'},{value:'ytd',label:'YTD'},{value:'all',label:'All'}]} />
```

For full section switching prefer `Tabs`; reserve this for short toggles.
