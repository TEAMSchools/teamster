import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-tabs{ display:flex; gap:4px; border-bottom:var(--border-width-strong) solid var(--border-subtle); }
.kf-tab{
  appearance:none; border:none; background:none; cursor:pointer;
  font-family:var(--font-brand); font-weight:700; text-transform:uppercase; letter-spacing:.04em;
  font-size:13px; color:var(--text-muted); padding:12px 16px; position:relative;
  transition:color var(--dur-fast) var(--ease-standard);
}
.kf-tab:hover{ color:var(--text-strong); }
.kf-tab::after{
  content:''; position:absolute; left:0; right:0; bottom:-2px; height:3px;
  background:var(--brand-accent); border-radius:var(--radius-pill) var(--radius-pill) 0 0;
  transform:scaleX(0); transform-origin:center; transition:transform var(--dur-base) var(--ease-out);
}
.kf-tab--active{ color:var(--text-strong); }
.kf-tab--active::after{ transform:scaleX(1); }
.kf-tab:focus-visible{ outline:none; box-shadow:var(--ring); border-radius:var(--radius-sm); }
`;

/**
 * Tabs — underline tab bar. Controlled via value / onChange.
 */
export function Tabs({
  tabs = [],          // [{value,label}] or string[]
  value,
  onChange = () => {},
  className = '',
  ...rest
}) {
  useDSStyle('kf-tabs', CSS);
  const items = tabs.map((t) => (typeof t === 'string' ? { value: t, label: t } : t));
  const active = value ?? items[0]?.value;
  return (
    <div className={['kf-tabs', className].filter(Boolean).join(' ')} role="tablist" {...rest}>
      {items.map((t) => (
        <button
          key={t.value}
          role="tab"
          aria-selected={t.value === active}
          className={['kf-tab', t.value === active ? 'kf-tab--active' : ''].filter(Boolean).join(' ')}
          onClick={() => onChange(t.value)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
