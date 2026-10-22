import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-card{
  background:var(--surface-card);
  border:var(--border-width) solid var(--border-subtle);
  border-radius:var(--radius-lg);
  overflow:hidden;
  transition:box-shadow var(--dur-base) var(--ease-standard), transform var(--dur-base) var(--ease-standard);
}
.kf-card--pad{ padding:var(--pad-card); }
.kf-card--sm{ box-shadow:var(--shadow-sm); }
.kf-card--md{ box-shadow:var(--shadow-md); }
.kf-card--lg{ box-shadow:var(--shadow-lg); }
.kf-card--flat{ box-shadow:none; }
.kf-card--pop{ border:var(--border-width-strong) solid var(--kipp-indigo); box-shadow:var(--shadow-pop); border-radius:var(--radius-md); }
.kf-card--inverse{ background:var(--kipp-indigo); border-color:transparent; color:var(--text-inverse); }
.kf-card--accentbar{ border-top:5px solid var(--brand-accent); }
.kf-card--interactive{ cursor:pointer; }
.kf-card--interactive:hover{ box-shadow:var(--shadow-lg); transform:translateY(-3px); }
`;

/**
 * Card — the base surface container. Square-ish, bold, lightly raised.
 */
export function Card({
  children,
  elevation = 'sm',
  pad = true,
  pop = false,
  inverse = false,
  accentBar = false,
  interactive = false,
  className = '',
  ...rest
}) {
  useDSStyle('kf-card', CSS);
  const cls = [
    'kf-card',
    pop ? 'kf-card--pop' : `kf-card--${elevation}`,
    pad ? 'kf-card--pad' : '',
    inverse ? 'kf-card--inverse' : '',
    accentBar ? 'kf-card--accentbar' : '',
    interactive ? 'kf-card--interactive' : '',
    className,
  ].filter(Boolean).join(' ');
  return <div className={cls} {...rest}>{children}</div>;
}
