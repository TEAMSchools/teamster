import React from 'react';

export type StatSize = 'sm' | 'md' | 'lg';
export type StatTone = 'default' | 'accent' | 'inverse';

export interface StatTrend {
  dir: 'up' | 'down';
  text: string;
}

export interface StatCalloutProps extends React.HTMLAttributes<HTMLDivElement> {
  /** The headline figure, e.g. "95.2%" or "9,000". */
  value: React.ReactNode;
  /** Uppercase label above the value. */
  label?: React.ReactNode;
  /** Supporting line below. */
  sub?: React.ReactNode;
  /** @default 'md' */
  size?: StatSize;
  /** 'inverse' for use on indigo; 'accent' colors the figure. @default 'default' */
  tone?: StatTone;
  /** Optional trend indicator. */
  trend?: StatTrend | null;
}

/**
 * The brand's signature big-number metric block (tabular figures).
 *
 * @startingPoint section="Display" subtitle="Big-number metric callouts for reports & dashboards" viewport="700x200"
 */
export function StatCallout(props: StatCalloutProps): JSX.Element;
