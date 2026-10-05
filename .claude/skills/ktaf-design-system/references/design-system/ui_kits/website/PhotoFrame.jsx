/**
 * PhotoFrame — honest stand-in for brand photography.
 * The brand uses real, warm, candid student/teacher photography with
 * SQUARE corners and no filters. We have no licensed photos in this
 * system, so this renders a labeled placeholder that respects the
 * square-corner rule. Swap for a real <img> in production.
 */
function PhotoFrame({ label = 'Photography', ratio = '4 / 3', tone = 'indigo', className = '', style = {}, ...rest }) {
  const bg = {
    indigo: 'var(--indigo-100)',
    blue: 'var(--blue-100)',
    orange: 'var(--orange-100)',
    green: 'var(--green-100)',
  }[tone] || 'var(--indigo-100)';
  const fg = {
    indigo: 'var(--indigo-600)',
    blue: 'var(--blue-700)',
    orange: 'var(--orange-700)',
    green: 'var(--green-700)',
  }[tone] || 'var(--indigo-600)';
  return (
    <div
      className={className}
      style={{
        aspectRatio: ratio,
        background: bg,
        borderRadius: 'var(--radius-photo)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: fg,
        overflow: 'hidden',
        position: 'relative',
        ...style,
      }}
      {...rest}
    >
      <svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.6 }}>
        <rect x="3" y="5" width="18" height="14" rx="0" />
        <circle cx="9" cy="10" r="2" />
        <path d="M3 17l5-4 4 3 3-2 6 5" />
      </svg>
      <span style={{
        position: 'absolute', bottom: 8, right: 10,
        fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 10,
        textTransform: 'uppercase', letterSpacing: '.08em', opacity: 0.55,
      }}>{label}</span>
    </div>
  );
}

window.PhotoFrame = PhotoFrame;
