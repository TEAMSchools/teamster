import React from 'react';

export interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Render as selected (indigo fill). */
  selected?: boolean;
  /** Make the chip clickable (hover affordance + pointer). */
  selectable?: boolean;
  /** Optional leading dot color (e.g. a viz color). */
  dotColor?: string | null;
  /** When provided, renders a removable "×"; called on click. */
  onRemove?: ((e: React.MouseEvent) => void) | null;
  children?: React.ReactNode;
}

/** Filter / category chip — selectable and removable variants. */
export function Tag(props: TagProps): JSX.Element;
