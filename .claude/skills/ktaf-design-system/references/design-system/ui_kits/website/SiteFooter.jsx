const COLS = [
  { h: 'Schools', links: ['Find a school', 'Apply now', 'School calendar', 'Transportation', 'Meals'] },
  { h: 'Families', links: ['Family portal', 'Student support', 'Special education', 'Title I', 'Contact us'] },
  { h: 'Join our team', links: ['Teach with us', 'Open roles', 'Why KIPP', 'Leadership', 'Benefits'] },
  { h: 'About', links: ['Our mission', 'Results', 'News', 'Board', 'Support us'] },
];

function SiteFooter() {
  return (
    <footer style={{ background: 'var(--indigo-900)', color: '#fff' }}>
      <div style={{ maxWidth: 'var(--container-max)', margin: '0 auto', padding: 'var(--space-16) var(--space-8) var(--space-10)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr repeat(4, 1fr)', gap: 'var(--space-8)' }}>
          <div>
            <img src="../../assets/logo-white-trimmed.png" alt="KIPP NJ | Miami" style={{ height: 40 }} />
            <p style={{ fontFamily: 'var(--font-sans)', fontSize: 14, lineHeight: 1.6, color: 'var(--indigo-200)', marginTop: 16, maxWidth: '30ch' }}>
              Free, public charter schools in Newark, Camden, Paterson, and Miami.
            </p>
          </div>
          {COLS.map((c) => (
            <div key={c.h}>
              <h4 style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 12, textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--brand-accent)', marginBottom: 14 }}>{c.h}</h4>
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 9 }}>
                {c.links.map((l) => (
                  <li key={l}><a href="#" style={{ fontFamily: 'var(--font-sans)', fontSize: 14, color: 'var(--indigo-100)' }}>{l}</a></li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div style={{ borderTop: '1px solid rgba(255,255,255,.12)', marginTop: 'var(--space-12)', paddingTop: 'var(--space-6)', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <span style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--indigo-300)' }}>© 2026 KIPP New Jersey &amp; KIPP Miami. All rights reserved.</span>
          <span style={{ fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--indigo-300)' }}>Privacy · Accessibility · Non-discrimination</span>
        </div>
      </div>
    </footer>
  );
}

window.SiteFooter = SiteFooter;
