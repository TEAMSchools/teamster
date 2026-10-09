import React from 'react';

export interface SwitchProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Label text beside the toggle. */
  label?: React.ReactNode;
}

/** Labeled on/off toggle (green when on). */
export function Switch(props: SwitchProps): JSX.Element;
