import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-switch{ display:inline-flex; align-items:center; gap:10px; cursor:pointer; font-family:var(--font-sans); font-size:15px; color:var(--text-body); }
.kf-switch input{ position:absolute; opacity:0; width:0; height:0; }
.kf-switch__track{
  width:42px; height:24px; flex:none; border-radius:var(--radius-pill);
  background:var(--neutral-300); position:relative;
  transition:background var(--dur-base) var(--ease-standard);
}
.kf-switch__thumb{
  position:absolute; top:3px; left:3px; width:18px; height:18px; border-radius:var(--radius-pill);
  background:var(--kipp-white); box-shadow:var(--shadow-sm);
  transition:transform var(--dur-base) var(--ease-spring);
}
.kf-switch input:checked + .kf-switch__track{ background:var(--status-success); }
.kf-switch input:checked + .kf-switch__track .kf-switch__thumb{ transform:translateX(18px); }
.kf-switch input:focus-visible + .kf-switch__track{ box-shadow:var(--ring); }
.kf-switch input:disabled + .kf-switch__track{ opacity:.5; }
`;

/**
 * Switch — labeled on/off toggle.
 */
export function Switch({
  label,
  className = '',
  ...rest
}) {
  useDSStyle('kf-switch', CSS);
  return (
    <label className={['kf-switch', className].filter(Boolean).join(' ')}>
      <input type="checkbox" role="switch" {...rest} />
      <span className="kf-switch__track"><span className="kf-switch__thumb" /></span>
      {label && <span className="kf-switch__label">{label}</span>}
    </label>
  );
}
