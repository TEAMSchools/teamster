const { Avatar } = window.KIPPNJMiamiDesignSystem_1916b9;

const NAV = [
  { id: 'overview', label: 'Overview', icon: 'M3 12l9-9 9 9M5 10v10h14V10' },
  { id: 'academics', label: 'Academics', icon: 'M4 19V5h16v14M4 12h16' },
  { id: 'attendance', label: 'Attendance', icon: 'M8 2v4M16 2v4M3 9h18M5 5h14v15H5z' },
  { id: 'enrollment', label: 'Enrollment', icon: 'M16 21v-2a4 4 0 0 0-8 0v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z' },
  { id: 'staff', label: 'Staff & culture', icon: 'M17 21v-2a4 4 0 0 0-3-3.9M9 21v-2a4 4 0 0 0-4-4H5M12 7a3 3 0 1 0 0-6 3 3 0 0 0 0 6z' },
];

function DashSidebar({ active, onNav }) {
  return (
    <aside style={{
      width: 244, flex: 'none', background: 'var(--kipp-indigo)', color: '#fff',
      display: 'flex', flexDirection: 'column', height: '100vh', position: 'sticky', top: 0,
    }}>
      <div style={{ padding: '20px 20px 18px', borderBottom: '1px solid rgba(255,255,255,.12)' }}>
        <img src="../../assets/logo-white-trimmed.png" alt="KIPP NJ | Miami Data" style={{ height: 30 }} />
      </div>
      <nav style={{ padding: 12, display: 'grid', gap: 2, flex: 1 }}>
        <div style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 10, textTransform: 'uppercase', letterSpacing: '.12em', color: 'var(--indigo-300)', padding: '10px 12px 6px' }}>Network data</div>
        {NAV.map((n) => {
          const on = n.id === active;
          return (
            <button key={n.id} onClick={() => onNav(n.id)} style={{
              display: 'flex', alignItems: 'center', gap: 11, width: '100%', textAlign: 'left',
              background: on ? 'rgba(255,255,255,.12)' : 'transparent', border: 'none', cursor: 'pointer',
              padding: '11px 12px', borderRadius: 'var(--radius-md)', color: on ? '#fff' : 'var(--indigo-100)',
              fontFamily: 'var(--font-brand)', fontWeight: 600, fontSize: 13.5, letterSpacing: '.01em',
              borderLeft: on ? '3px solid var(--brand-accent)' : '3px solid transparent',
            }}>
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d={n.icon} /></svg>
              {n.label}
            </button>
          );
        })}
      </nav>
      <div style={{ padding: 14, borderTop: '1px solid rgba(255,255,255,.12)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Avatar name="Data Team" tone="accent" size="sm" />
        <div style={{ lineHeight: 1.2 }}>
          <div style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 13, color: '#fff' }}>Data Team</div>
          <div style={{ fontFamily: 'var(--font-sans)', fontSize: 11.5, color: 'var(--indigo-300)' }}>Research &amp; Analytics</div>
        </div>
      </div>
    </aside>
  );
}

window.DashSidebar = DashSidebar;
