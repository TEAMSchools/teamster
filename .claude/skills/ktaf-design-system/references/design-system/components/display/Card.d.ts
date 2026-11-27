import React from 'react';

export type CardElevation = 'flat' | 'sm' | 'md' | 'lg';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Soft drop shadow level. @default 'sm' */
  elevation?: CardElevation;
  /** Apply default card padding. @default true */
  pad?: boolean;
  /** Use the hard-offset indigo "pop" emphasis treatment instead of a soft shadow. */
  pop?: boolean;
  /** Indigo fill with white text. */
  inverse?: boolean;
  /** Add a thick accent bar across the top (region color). */
  accentBar?: boolean;
  /** Lift on hover; pair with onClick. */
  interactive?: boolean;
  children?: React.ReactNode;
}

/**
 * Base surface container — bold, lightly raised, square corners.
 *
 * @startingPoint section="Display" subtitle="Surface cards — soft, pop, inverse, accent-bar" viewport="700x260"
 */
export function Card(props: CardProps): JSX.Element;
