const { SegmentedControl, Button } = window.KIPPNJMiamiDesignSystem_1916b9;

const SCHOOLS = ['Network — all schools', 'KIPP Rise Academy', 'KIPP Newark Collegiate', 'KIPP Cooper Norcross', 'KIPP Miami Prep'];

function DashTopbar({ school, onSchool, range, onRange }) {
  const [open, setOpen] = React.useState(false);
  return (
    <header style={{
      height: 68, flex: 'none', background: 'var(--surface-card)', borderBottom: '1px solid var(--border-subtle)',
      display: 'flex', alignItems: 'center', gap: 'var(--space-5)', padding: '0 var(--space-8)', position: 'sticky', top: 0, zIndex: 30,
    }}>
      {/* School selector */}
      <div style={{ position: 'relative' }}>
        <button onClick={() => setOpen((o) => !o)} style={{
          display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer',
          background: 'var(--surface-sunken)', border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-md)', padding: '9px 14px',
          fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 14, color: 'var(--text-strong)',
        }}>
          {school}
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 6l4 4 4-4" /></svg>
        </button>
        {open && (
          <div style={{ position: 'absolute', top: 'calc(100% + 6px)', left: 0, minWidth: 260, background: '#fff', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)', padding: 6, zIndex: 40 }}>
            {SCHOOLS.map((s) => (
              <button key={s} onClick={() => { onSchool(s); setOpen(false); }} style={{
                display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
                background: s === school ? 'var(--indigo-50)' : 'transparent', border: 'none',
                padding: '9px 12px', borderRadius: 'var(--radius-sm)',
                fontFamily: 'var(--font-sans)', fontSize: 14, color: s === school ? 'var(--kipp-indigo)' : 'var(--text-body)', fontWeight: s === school ? 700 : 400,
              }}>{s}</button>
            ))}
          </div>
        )}
      </div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
        <SegmentedControl value={range} onChange={onRange} options={[{ value: 'q', label: 'Quarter' }, { value: 'ytd', label: 'YTD' }, { value: 'multi', label: 'Multi-yr' }]} />
        <Button variant="secondary" size="sm" iconLeft={<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12M7 10l5 5 5-5M5 21h14" /></svg>}>Export</Button>
      </div>
    </header>
  );
}

window.DashTopbar = DashTopbar;
