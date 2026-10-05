import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-seg{ display:inline-flex; background:var(--surface-muted); border-radius:var(--radius-md); padding:4px; gap:2px; }
.kf-seg__opt{
  appearance:none; border:none; cursor:pointer; background:transparent;
  font-family:var(--font-brand); font-weight:700; text-transform:uppercase; letter-spacing:.04em;
  font-size:12px; color:var(--text-muted); padding:8px 16px; border-radius:var(--radius-sm);
  transition:background var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}
.kf-seg__opt:hover{ color:var(--text-strong); }
.kf-seg__opt--active{ background:var(--surface-card); color:var(--text-strong); box-shadow:var(--shadow-sm); }
.kf-seg__opt:focus-visible{ outline:none; box-shadow:var(--ring); }
`;

/**
 * SegmentedControl — compact 2–4 option switch for tight toolbars.
 */
export function SegmentedControl({
  options = [],
  value,
  onChange = () => {},
  className = '',
  ...rest
}) {
  useDSStyle('kf-seg', CSS);
  const items = options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o));
  const active = value ?? items[0]?.value;
  return (
    <div className={['kf-seg', className].filter(Boolean).join(' ')} role="group" {...rest}>
      {items.map((o) => (
        <button
          key={o.value}
          className={['kf-seg__opt', o.value === active ? 'kf-seg__opt--active' : ''].filter(Boolean).join(' ')}
          aria-pressed={o.value === active}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
