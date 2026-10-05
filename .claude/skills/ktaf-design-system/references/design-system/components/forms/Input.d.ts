import React from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Uppercase field label. */
  label?: React.ReactNode;
  /** Helper text below the field. */
  hint?: React.ReactNode;
  /** Error message — also sets the invalid styling. */
  error?: React.ReactNode;
  /** Mark the label with a required asterisk. */
  required?: boolean;
  /** Leading icon node. */
  icon?: React.ReactNode;
}

/** Labeled text field with hint / error states. */
export function Input(props: InputProps): JSX.Element;
