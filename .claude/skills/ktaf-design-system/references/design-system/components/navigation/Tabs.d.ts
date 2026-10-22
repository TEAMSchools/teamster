import React from 'react';

export interface TabItem {
  value: string;
  label: React.ReactNode;
}

export interface TabsProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
  /** Tabs as `{value,label}` objects or plain strings. */
  tabs: Array<TabItem | string>;
  /** Active tab value (controlled). */
  value?: string;
  /** Fired with the new value when a tab is clicked. */
  onChange?: (value: string) => void;
}

/**
 * Underline tab bar with an animated accent indicator.
 *
 * @startingPoint section="Navigation" subtitle="Underline tab bar for switching views" viewport="700x120"
 */
export function Tabs(props: TabsProps): JSX.Element;
