Labeled dropdown for choosing one option; use for region, grade, school filters.

```jsx
<Select label="Region" placeholder="Choose a region"
  options={['Newark','Camden','Paterson','Miami']} />
<Select label="Grade" options={[{value:'k',label:'Kindergarten'},{value:'1',label:'Grade 1'}]} />
```

- Pass `options` as strings or `{value,label}`. `placeholder` adds a disabled lead option.
- Styled to match `Input`; passes through native `<select>` props.
