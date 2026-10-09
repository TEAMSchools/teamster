import React from 'react';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  /** Uppercase field label. */
  label?: React.ReactNode;
  /** Helper text below. */
  hint?: React.ReactNode;
  /** Required asterisk. */
  required?: boolean;
  /** Options as `{value,label}` objects or plain strings. */
  options?: Array<SelectOption | string>;
  /** Disabled leading placeholder option. */
  placeholder?: string | null;
}

/** Labeled native dropdown styled to match Input. */
export function Select(props: SelectProps): JSX.Element;
