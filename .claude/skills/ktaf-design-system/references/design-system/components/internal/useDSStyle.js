import React from 'react';

/**
 * Shared one-time <style> injector for design-system components.
 * Keeps components self-contained while still giving real
 * :hover / :focus / :active states driven by brand tokens.
 */
const injected = new Set();
export function useDSStyle(id, css) {
  if (typeof document === 'undefined') return;
  if (injected.has(id)) return;
  injected.add(id);
  const el = document.createElement('style');
  el.setAttribute('data-ds', id);
  el.textContent = css;
  document.head.appendChild(el);
}
