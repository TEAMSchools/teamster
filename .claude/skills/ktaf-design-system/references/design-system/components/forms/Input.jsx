import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-field{ display:flex; flex-direction:column; gap:6px; }
.kf-field__label{ font-family:var(--font-brand); font-weight:700; text-transform:uppercase; letter-spacing:.05em; font-size:12px; color:var(--text-strong); }
.kf-field__req{ color:var(--status-danger); margin-left:2px; }
.kf-input{
  font-family:var(--font-sans); font-size:15px; color:var(--text-body);
  background:var(--surface-card); border:var(--border-width) solid var(--border-default);
  border-radius:var(--radius-md); padding:11px 13px; width:100%;
  transition:border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}
.kf-input::placeholder{ color:var(--text-subtle); }
.kf-input:hover{ border-color:var(--neutral-400); }
.kf-input:focus{ outline:none; border-color:var(--kipp-indigo); box-shadow:var(--ring); }
.kf-input--invalid{ border-color:var(--status-danger); }
.kf-input--invalid:focus{ box-shadow:0 0 0 3px var(--red-200); }
.kf-input:disabled{ background:var(--surface-muted); color:var(--text-subtle); cursor:not-allowed; }
.kf-field__hint{ font-family:var(--font-sans); font-size:12.5px; color:var(--text-muted); }
.kf-field__hint--err{ color:var(--status-danger); }
.kf-input__wrap{ position:relative; display:flex; align-items:center; }
.kf-input__icon{ position:absolute; left:12px; display:flex; color:var(--text-subtle); pointer-events:none; }
.kf-input__icon ~ .kf-input{ padding-left:38px; }
`;

/**
 * Input — labeled text field with hint / error states.
 */
export function Input({
  label,
  hint = null,
  error = null,
  required = false,
  icon = null,
  id,
  className = '',
  ...rest
}) {
  useDSStyle('kf-input', CSS);
  const fieldId = id || (label ? `kf-${String(label).toLowerCase().replace(/\s+/g, '-')}` : undefined);
  const invalid = Boolean(error);
  return (
    <div className={['kf-field', className].filter(Boolean).join(' ')}>
      {label && (
        <label className="kf-field__label" htmlFor={fieldId}>
          {label}{required && <span className="kf-field__req">*</span>}
        </label>
      )}
      <span className="kf-input__wrap">
        {icon && <span className="kf-input__icon">{icon}</span>}
        <input
          id={fieldId}
          className={['kf-input', invalid ? 'kf-input--invalid' : ''].filter(Boolean).join(' ')}
          aria-invalid={invalid}
          {...rest}
        />
      </span>
      {error ? (
        <span className="kf-field__hint kf-field__hint--err">{error}</span>
      ) : hint ? (
        <span className="kf-field__hint">{hint}</span>
      ) : null}
    </div>
  );
}
