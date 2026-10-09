import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-iconbtn{
  --_bg:transparent; --_fg:var(--kipp-indigo); --_bd:transparent;
  display:inline-flex; align-items:center; justify-content:center;
  border:var(--border-width-strong) solid var(--_bd); border-radius:var(--radius-md);
  background:var(--_bg); color:var(--_fg); cursor:pointer; padding:0;
  transition:background var(--dur-fast) var(--ease-standard), transform var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}
.kf-iconbtn svg{ width:60%; height:60%; }
.kf-iconbtn:hover{ background:var(--indigo-50); }
.kf-iconbtn:active{ transform:scale(var(--press-scale)); }
.kf-iconbtn:focus-visible{ outline:none; box-shadow:var(--ring); }
.kf-iconbtn[disabled]{ opacity:.45; cursor:not-allowed; }
.kf-iconbtn--sm{ width:32px; height:32px; }
.kf-iconbtn--md{ width:40px; height:40px; }
.kf-iconbtn--lg{ width:48px; height:48px; }
.kf-iconbtn--solid{ --_bg:var(--kipp-indigo); --_fg:var(--kipp-white); }
.kf-iconbtn--solid:hover{ background:var(--indigo-700); }
.kf-iconbtn--accent{ --_bg:var(--brand-accent); --_fg:var(--brand-on-accent); }
.kf-iconbtn--outline{ --_bd:var(--border-default); }
.kf-iconbtn--pill{ border-radius:var(--radius-pill); }
`;

/**
 * IconButton — square (or pill) tappable control wrapping a single icon.
 */
export function IconButton({
  children,
  variant = 'ghost',
  size = 'md',
  pill = false,
  label,
  className = '',
  ...rest
}) {
  useDSStyle('kf-iconbtn', CSS);
  const cls = [
    'kf-iconbtn',
    `kf-iconbtn--${variant}`,
    `kf-iconbtn--${size}`,
    pill ? 'kf-iconbtn--pill' : '',
    className,
  ].filter(Boolean).join(' ');
  return (
    <button type="button" aria-label={label} title={label} className={cls} {...rest}>
      {children}
    </button>
  );
}
