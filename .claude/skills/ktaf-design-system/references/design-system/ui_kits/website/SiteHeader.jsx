const NAV = ['Our Schools', 'Apply', 'Academics', 'Careers', 'About'];
const REGIONS = [
  { id: 'newark', label: 'Newark' },
  { id: 'camden', label: 'Camden' },
  { id: 'paterson', label: 'Paterson' },
  { id: 'miami', label: 'Miami' },
];

function SiteHeader({ region, onRegion, onApply }) {
  const [open, setOpen] = React.useState(false);
  return (
    <header style={{ position: 'sticky', top: 0, zIndex: 40, background: 'var(--kipp-indigo)' }}>
      <div style={{
        maxWidth: 'var(--container-max)', margin: '0 auto', padding: '0 var(--space-8)',
        height: 72, display: 'flex', alignItems: 'center', gap: 'var(--space-8)',
      }}>
        {/* Logo */}
        <a href="#" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <img src="../../assets/logo-white-trimmed.png" alt="KIPP NJ | Miami" style={{ height: 34 }} />
        </a>

        {/* Nav */}
        <nav style={{ display: 'flex', gap: 'var(--space-6)', marginLeft: 'var(--space-4)' }}>
          {NAV.map((n) => (
            <a key={n} href="#" style={{
              fontFamily: 'var(--font-brand)', fontWeight: 600, fontSize: 13.5,
              textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--indigo-100)',
            }}>{n}</a>
          ))}
        </nav>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
          {/* Region picker */}
          <div style={{ position: 'relative' }}>
            <button onClick={() => setOpen((o) => !o)} style={{
              display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer',
              background: 'rgba(255,255,255,.10)', border: '1px solid rgba(255,255,255,.18)',
              color: '#fff', borderRadius: 'var(--radius-md)', padding: '8px 12px',
              fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 12,
              textTransform: 'uppercase', letterSpacing: '.04em',
            }}>
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 21s-7-6.3-7-11a7 7 0 0 1 14 0c0 4.7-7 11-7 11z"/><circle cx="12" cy="10" r="2.3"/></svg>
              {REGIONS.find((r) => r.id === region)?.label}
              <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 6l4 4 4-4"/></svg>
            </button>
            {open && (
              <div style={{
                position: 'absolute', top: 'calc(100% + 6px)', right: 0, minWidth: 160,
                background: '#fff', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)',
                padding: 6, zIndex: 50,
              }}>
                {REGIONS.map((r) => (
                  <button key={r.id} onClick={() => { onRegion(r.id); setOpen(false); }} style={{
                    display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
                    background: r.id === region ? 'var(--indigo-50)' : 'transparent', border: 'none',
                    padding: '9px 12px', borderRadius: 'var(--radius-sm)',
                    fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 13,
                    textTransform: 'uppercase', letterSpacing: '.03em',
                    color: r.id === region ? 'var(--kipp-indigo)' : 'var(--text-body)',
                  }}>{r.label}</button>
                ))}
              </div>
            )}
          </div>
          <button onClick={onApply} style={{
            background: 'var(--brand-accent)', color: 'var(--brand-on-accent)', border: 'none',
            borderRadius: 'var(--radius-md)', padding: '11px 20px', cursor: 'pointer',
            fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 13,
            textTransform: 'uppercase', letterSpacing: '.04em',
          }}>Enroll now</button>
        </div>
      </div>
    </header>
  );
}

window.SiteHeader = SiteHeader;
