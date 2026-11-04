import React from 'react';

export interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Label text beside the box. */
  label?: React.ReactNode;
  /** Round shape (use for single-select-style lists). */
  round?: boolean;
}

/** Labeled boolean checkbox. */
export function Checkbox(props: CheckboxProps): JSX.Element;
