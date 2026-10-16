import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-stat{ display:flex; flex-direction:column; gap:4px; }
.kf-stat__value{
  font-family:var(--font-mono); font-variant-numeric:tabular-nums;
  font-weight:700; line-height:1; color:var(--text-strong); letter-spacing:-.01em;
}
.kf-stat--sm .kf-stat__value{ font-size:30px; }
.kf-stat--md .kf-stat__value{ font-size:44px; }
.kf-stat--lg .kf-stat__value{ font-size:64px; }
.kf-stat--accent .kf-stat__value{ color:var(--brand-accent); }
.kf-stat--inverse .kf-stat__value{ color:var(--kipp-white); }
.kf-stat__label{
  font-family:var(--font-brand); font-weight:700; text-transform:uppercase;
  letter-spacing:.06em; font-size:12px; color:var(--text-muted);
}
.kf-stat--inverse .kf-stat__label{ color:var(--indigo-200); }
.kf-stat__sub{ font-family:var(--font-sans); font-size:13px; color:var(--text-muted); }
.kf-stat--inverse .kf-stat__sub{ color:var(--indigo-200); }
.kf-stat__trend{ display:inline-flex; align-items:center; gap:4px; font-family:var(--font-sans); font-weight:600; font-size:13px; }
.kf-stat__trend--up{ color:var(--green-700); }
.kf-stat__trend--down{ color:var(--red-700); }
`;

/**
 * StatCallout — the brand's signature big-number metric block.
 */
export function StatCallout({
  value,
  label,
  sub = null,
  size = 'md',
  tone = 'default',
  trend = null,          // { dir: 'up'|'down', text: '+4.2 pts' }
  className = '',
  ...rest
}) {
  useDSStyle('kf-stat', CSS);
  const cls = ['kf-stat', `kf-stat--${size}`, `kf-stat--${tone}`, className].filter(Boolean).join(' ');
  return (
    <div className={cls} {...rest}>
      {label && <span className="kf-stat__label">{label}</span>}
      <span className="kf-stat__value">{value}</span>
      {trend && (
        <span className={`kf-stat__trend kf-stat__trend--${trend.dir}`}>
          <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            {trend.dir === 'up' ? <path d="M3 11l5-5 5 5"/> : <path d="M3 5l5 5 5-5"/>}
          </svg>
          {trend.text}
        </span>
      )}
      {sub && <span className="kf-stat__sub">{sub}</span>}
    </div>
  );
}
