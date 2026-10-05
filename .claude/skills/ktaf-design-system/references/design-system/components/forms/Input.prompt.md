Labeled text field; use in enrollment forms, search, contact forms.

```jsx
<Input label="Family email" type="email" placeholder="you@email.com" required />
<Input label="Student ID" hint="6 digits on the report card" />
<Input label="ZIP" error="Enter a valid NJ ZIP" />
```

- `hint` shows helper text; `error` overrides it and applies invalid styling.
- `icon` renders a leading icon. Passes through all native `<input>` props.
