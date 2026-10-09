import React from 'react';

export interface SegmentOption {
  value: string;
  label: React.ReactNode;
}

export interface SegmentedControlProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
  /** 2–4 options as `{value,label}` or strings. */
  options: Array<SegmentOption | string>;
  /** Active value (controlled). */
  value?: string;
  /** Fired with the new value. */
  onChange?: (value: string) => void;
}

/** Compact 2–4 option switch for tight toolbars. */
export function SegmentedControl(props: SegmentedControlProps): JSX.Element;
