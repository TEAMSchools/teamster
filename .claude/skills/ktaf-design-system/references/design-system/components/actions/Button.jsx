import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-btn{
  --_bg:var(--kipp-indigo); --_fg:var(--kipp-white); --_bd:transparent;
  display:inline-flex; align-items:center; justify-content:center; gap:8px;
  font-family:var(--font-brand); font-weight:600; text-transform:uppercase;
  letter-spacing:.04em; line-height:1; white-space:nowrap; cursor:pointer;
  border:var(--border-width-strong) solid var(--_bd); border-radius:var(--radius-md);
  background:var(--_bg); color:var(--_fg);
  transition:transform var(--dur-fast) var(--ease-standard),
             background var(--dur-fast) var(--ease-standard),
             box-shadow var(--dur-fast) var(--ease-standard), filter var(--dur-fast) var(--ease-standard);
}
.kf-btn:hover{ filter:brightness(1.06); transform:translateY(var(--hover-lift)); }
.kf-btn:active{ transform:scale(var(--press-scale)); filter:brightness(.96); }
.kf-btn:focus-visible{ outline:none; box-shadow:var(--ring); }
.kf-btn[disabled]{ opacity:.45; cursor:not-allowed; transform:none; filter:none; }

/* sizes */
.kf-btn--sm{ font-size:12px; padding:8px 14px; }
.kf-btn--md{ font-size:13px; padding:11px 20px; }
.kf-btn--lg{ font-size:15px; padding:15px 28px; }

/* variants */
.kf-btn--primary{ --_bg:var(--kipp-indigo); --_fg:var(--kipp-white); }
.kf-btn--accent{ --_bg:var(--brand-accent); --_fg:var(--brand-on-accent); }
.kf-btn--secondary{ --_bg:transparent; --_fg:var(--kipp-indigo); --_bd:var(--kipp-indigo); }
.kf-btn--secondary:hover{ background:var(--indigo-50); filter:none; }
.kf-btn--ghost{ --_bg:transparent; --_fg:var(--kipp-indigo); --_bd:transparent; }
.kf-btn--ghost:hover{ background:var(--indigo-50); filter:none; }
.kf-btn--block{ width:100%; }
`;

/**
 * Button — the primary brand action. Bold, all-caps, confident.
 */
export function Button({
  children,
  variant = 'primary',
  size = 'md',
  block = false,
  iconLeft = null,
  iconRight = null,
  type = 'button',
  className = '',
  ...rest
}) {
  useDSStyle('kf-btn', CSS);
  const cls = [
    'kf-btn',
    `kf-btn--${variant}`,
    `kf-btn--${size}`,
    block ? 'kf-btn--block' : '',
    className,
  ].filter(Boolean).join(' ');
  return (
    <button type={type} className={cls} {...rest}>
      {iconLeft}
      {children}
      {iconRight}
    </button>
  );
}
