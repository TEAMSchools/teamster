Filter or category chip; use for school filters, subject tags, removable selections.

```jsx
<Tag selectable selected onClick={toggle}>Elementary</Tag>
<Tag dotColor="var(--viz-2)">Math</Tag>
<Tag onRemove={() => drop(id)}>Newark</Tag>
```

- `selectable` adds hover affordance; `selected` fills indigo.
- `dotColor` shows a leading category dot; `onRemove` renders a × and fires on click.
