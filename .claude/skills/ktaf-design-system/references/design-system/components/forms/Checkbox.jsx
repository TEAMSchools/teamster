import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-check{ display:inline-flex; align-items:flex-start; gap:10px; cursor:pointer; font-family:var(--font-sans); font-size:15px; color:var(--text-body); }
.kf-check input{ position:absolute; opacity:0; width:0; height:0; }
.kf-check__box{
  width:20px; height:20px; flex:none; margin-top:1px;
  border:var(--border-width-strong) solid var(--border-default); border-radius:var(--radius-sm);
  background:var(--surface-card); display:inline-flex; align-items:center; justify-content:center;
  transition:background var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard);
}
.kf-check__box svg{ width:14px; height:14px; opacity:0; color:var(--kipp-white); transition:opacity var(--dur-fast) var(--ease-standard); }
.kf-check:hover .kf-check__box{ border-color:var(--kipp-indigo); }
.kf-check input:checked + .kf-check__box{ background:var(--kipp-indigo); border-color:var(--kipp-indigo); }
.kf-check input:checked + .kf-check__box svg{ opacity:1; }
.kf-check input:focus-visible + .kf-check__box{ box-shadow:var(--ring); }
.kf-check--round .kf-check__box{ border-radius:var(--radius-pill); }
.kf-check input:disabled ~ *{ opacity:.5; }
`;

/**
 * Checkbox — labeled boolean control (square, or round for single-choice lists).
 */
export function Checkbox({
  label,
  round = false,
  className = '',
  ...rest
}) {
  useDSStyle('kf-check', CSS);
  return (
    <label className={['kf-check', round ? 'kf-check--round' : '', className].filter(Boolean).join(' ')}>
      <input type="checkbox" {...rest} />
      <span className="kf-check__box">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 8.5l3.5 3.5L13 4.5"/></svg>
      </span>
      {label && <span className="kf-check__label">{label}</span>}
    </label>
  );
}
