import React from 'react';

export type ButtonVariant = 'primary' | 'accent' | 'secondary' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style. primary = indigo, accent = region color, secondary = outline, ghost = text. */
  variant?: ButtonVariant;
  /** Control size. @default 'md' */
  size?: ButtonSize;
  /** Stretch to full width of container. */
  block?: boolean;
  /** Icon node rendered before the label. */
  iconLeft?: React.ReactNode;
  /** Icon node rendered after the label. */
  iconRight?: React.ReactNode;
  children?: React.ReactNode;
}

/**
 * The primary brand action: bold, all-caps, confident.
 *
 * @startingPoint section="Actions" subtitle="Brand buttons — primary, accent, outline, ghost" viewport="700x180"
 */
export function Button(props: ButtonProps): JSX.Element;
