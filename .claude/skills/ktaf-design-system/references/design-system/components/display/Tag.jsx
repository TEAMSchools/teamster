import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-tag{
  display:inline-flex; align-items:center; gap:6px;
  font-family:var(--font-sans); font-weight:600; font-size:13px; line-height:1;
  padding:7px 12px; border-radius:var(--radius-pill);
  background:var(--surface-card); color:var(--text-body);
  border:var(--border-width) solid var(--border-default); cursor:default;
  transition:background var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
}
.kf-tag--selectable{ cursor:pointer; }
.kf-tag--selectable:hover{ border-color:var(--kipp-indigo); }
.kf-tag--selected{ background:var(--kipp-indigo); border-color:var(--kipp-indigo); color:var(--kipp-white); }
.kf-tag__x{ display:inline-flex; align-items:center; cursor:pointer; opacity:.55; }
.kf-tag__x:hover{ opacity:1; }
.kf-tag__dot{ width:8px; height:8px; border-radius:var(--radius-pill); flex:none; }
`;

/**
 * Tag — filter / category chip; selectable and removable variants.
 */
export function Tag({
  children,
  selected = false,
  selectable = false,
  dotColor = null,
  onRemove = null,
  className = '',
  ...rest
}) {
  useDSStyle('kf-tag', CSS);
  const cls = [
    'kf-tag',
    selectable ? 'kf-tag--selectable' : '',
    selected ? 'kf-tag--selected' : '',
    className,
  ].filter(Boolean).join(' ');
  return (
    <span className={cls} {...rest}>
      {dotColor && <span className="kf-tag__dot" style={{ background: dotColor }} />}
      {children}
      {onRemove && (
        <span
          className="kf-tag__x"
          role="button"
          aria-label="Remove"
          onClick={(e) => { e.stopPropagation(); onRemove(e); }}
        >
          <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 4l8 8M12 4l-8 8"/></svg>
        </span>
      )}
    </span>
  );
}
