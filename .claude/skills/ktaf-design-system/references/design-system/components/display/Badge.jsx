import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-badge{
  display:inline-flex; align-items:center; gap:5px;
  font-family:var(--font-brand); font-weight:700; text-transform:uppercase; letter-spacing:.05em;
  font-size:11px; line-height:1; padding:5px 9px; border-radius:var(--radius-pill);
  background:var(--neutral-100); color:var(--text-body); white-space:nowrap;
}
.kf-badge .kf-badge__dot{ width:6px; height:6px; border-radius:var(--radius-pill); background:currentColor; }
.kf-badge--neutral{ background:var(--neutral-100); color:var(--neutral-700); }
.kf-badge--indigo{ background:var(--indigo-100); color:var(--indigo-700); }
.kf-badge--success{ background:var(--status-success-surface); color:var(--green-700); }
.kf-badge--warning{ background:var(--status-warning-surface); color:var(--orange-700); }
.kf-badge--danger{ background:var(--status-danger-surface); color:var(--red-700); }
.kf-badge--info{ background:var(--status-info-surface); color:var(--blue-700); }
.kf-badge--solid{ background:var(--kipp-indigo); color:var(--kipp-white); }
.kf-badge--accent{ background:var(--brand-accent); color:var(--brand-on-accent); }
`;

/**
 * Badge — small status / category pill.
 */
export function Badge({
  children,
  tone = 'neutral',
  dot = false,
  className = '',
  ...rest
}) {
  useDSStyle('kf-badge', CSS);
  const cls = ['kf-badge', `kf-badge--${tone}`, className].filter(Boolean).join(' ');
  return (
    <span className={cls} {...rest}>
      {dot && <span className="kf-badge__dot" />}
      {children}
    </span>
  );
}
