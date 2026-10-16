import React from 'react';
import { useDSStyle } from '../internal/useDSStyle.js';

const CSS = `
.kf-avatar{
  display:inline-flex; align-items:center; justify-content:center;
  border-radius:var(--radius-pill); overflow:hidden; flex:none;
  font-family:var(--font-brand); font-weight:700; text-transform:uppercase;
  background:var(--indigo-100); color:var(--indigo-700);
  border:2px solid var(--surface-card);
}
.kf-avatar img{ width:100%; height:100%; object-fit:cover; border-radius:0; }
.kf-avatar--xs{ width:24px; height:24px; font-size:10px; }
.kf-avatar--sm{ width:32px; height:32px; font-size:12px; }
.kf-avatar--md{ width:44px; height:44px; font-size:15px; }
.kf-avatar--lg{ width:64px; height:64px; font-size:22px; }
.kf-avatar--accent{ background:var(--brand-accent); color:var(--brand-on-accent); }
.kf-avatar--indigo{ background:var(--kipp-indigo); color:var(--kipp-white); }
.kf-avatargroup{ display:inline-flex; }
.kf-avatargroup > .kf-avatar:not(:first-child){ margin-left:-10px; }
`;

function initials(name = '') {
  return name.trim().split(/\s+/).slice(0, 2).map((p) => p[0] || '').join('');
}

/**
 * Avatar — circular person/initials chip.
 */
export function Avatar({
  src = null,
  name = '',
  size = 'md',
  tone = 'default',
  className = '',
  ...rest
}) {
  useDSStyle('kf-avatar', CSS);
  const cls = ['kf-avatar', `kf-avatar--${size}`, tone !== 'default' ? `kf-avatar--${tone}` : '', className].filter(Boolean).join(' ');
  return (
    <span className={cls} title={name} {...rest}>
      {src ? <img src={src} alt={name} /> : initials(name)}
    </span>
  );
}

/** AvatarGroup — overlapping stack of avatars. */
export function AvatarGroup({ children, className = '', ...rest }) {
  useDSStyle('kf-avatar', CSS);
  return <span className={['kf-avatargroup', className].filter(Boolean).join(' ')} {...rest}>{children}</span>;
}
