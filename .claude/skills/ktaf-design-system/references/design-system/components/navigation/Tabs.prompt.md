Underline tab bar with an animated accent indicator; use to switch between report views or sections.

```jsx
const [tab, setTab] = React.useState('overview');
<Tabs value={tab} onChange={setTab}
  tabs={['Overview','Academics','Enrollment','Staff']} />
```

- Controlled: pass `value` + `onChange`. Tabs accept strings or `{value,label}`.
- The active underline uses the region accent color.
