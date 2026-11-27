import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-select__wrap{ position:relative; display:flex; align-items:center; }
.kf-select{
  appearance:none; -webkit-appearance:none;
  font-family:var(--font-sans); font-size:15px; color:var(--text-body);
  background:var(--surface-card); border:var(--border-width) solid var(--border-default);
  border-radius:var(--radius-md); padding:11px 38px 11px 13px; width:100%; cursor:pointer;
  transition:border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}
.kf-select:hover{ border-color:var(--neutral-400); }
.kf-select:focus{ outline:none; border-color:var(--kipp-indigo); box-shadow:var(--ring); }
.kf-select:disabled{ background:var(--surface-muted); color:var(--text-subtle); cursor:not-allowed; }
.kf-select__chev{ position:absolute; right:13px; pointer-events:none; color:var(--text-muted); display:flex; }
`;

/**
 * Select — labeled native dropdown styled to match Input.
 */
export function Select({
  label,
  hint = null,
  required = false,
  options = [],          // [{value,label}] or string[]
  placeholder = null,
  id,
  className = '',
  children,
  ...rest
}) {
  useDSStyle('kf-select', CSS);
  const fieldId = id || (label ? `kf-sel-${String(label).toLowerCase().replace(/\s+/g, '-')}` : undefined);
  const opts = options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o));
  return (
    <div className={['kf-field', className].filter(Boolean).join(' ')}>
      {label && (
        <label className="kf-field__label" htmlFor={fieldId}>
          {label}{required && <span className="kf-field__req">*</span>}
        </label>
      )}
      <span className="kf-select__wrap">
        <select id={fieldId} className="kf-select" {...rest}>
          {placeholder && <option value="" disabled>{placeholder}</option>}
          {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          {children}
        </select>
        <span className="kf-select__chev">
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6l4 4 4-4"/></svg>
        </span>
      </span>
      {hint && <span className="kf-field__hint">{hint}</span>}
    </div>
  );
}
