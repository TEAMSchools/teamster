Compact control wrapping a single icon; use for toolbars, nav, close/menu actions where a text label would be redundant.

```jsx
<IconButton label="Close" variant="ghost"><i data-lucide="x"></i></IconButton>
<IconButton label="Next" variant="solid" pill><i data-lucide="arrow-right"></i></IconButton>
```

- `variant`: `ghost` (default) · `solid` (indigo) · `accent` (region color) · `outline`
- `size`: `sm` · `md` · `lg`; `pill` makes it round. `label` is required for accessibility.
