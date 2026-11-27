import React from 'react';

export type BadgeTone =
  | 'neutral' | 'indigo' | 'success' | 'warning' | 'danger' | 'info' | 'solid' | 'accent';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Color tone. @default 'neutral' */
  tone?: BadgeTone;
  /** Show a leading status dot. */
  dot?: boolean;
  children?: React.ReactNode;
}

/** Small status or category pill, all-caps. */
export function Badge(props: BadgeProps): JSX.Element;
