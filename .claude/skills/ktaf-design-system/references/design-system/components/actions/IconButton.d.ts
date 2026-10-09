import React from 'react';

export type IconButtonVariant = 'ghost' | 'solid' | 'accent' | 'outline';
export type IconButtonSize = 'sm' | 'md' | 'lg';

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style. @default 'ghost' */
  variant?: IconButtonVariant;
  /** @default 'md' */
  size?: IconButtonSize;
  /** Use a fully round (pill) shape. */
  pill?: boolean;
  /** Accessible label (also used as tooltip) — required since there is no text. */
  label: string;
  /** Single icon node. */
  children?: React.ReactNode;
}

/** Square or pill control wrapping a single icon. */
export function IconButton(props: IconButtonProps): JSX.Element;
