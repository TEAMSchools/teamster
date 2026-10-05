import React from 'react';

export type AvatarSize = 'xs' | 'sm' | 'md' | 'lg';
export type AvatarTone = 'default' | 'accent' | 'indigo';

export interface AvatarProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Image URL; falls back to initials when absent. */
  src?: string | null;
  /** Full name — used for initials and tooltip. */
  name?: string;
  /** @default 'md' */
  size?: AvatarSize;
  /** Initials background. @default 'default' */
  tone?: AvatarTone;
}

/** Circular person / initials chip. */
export function Avatar(props: AvatarProps): JSX.Element;

export interface AvatarGroupProps extends React.HTMLAttributes<HTMLSpanElement> {
  children?: React.ReactNode;
}

/** Overlapping stack of avatars. */
export function AvatarGroup(props: AvatarGroupProps): JSX.Element;
