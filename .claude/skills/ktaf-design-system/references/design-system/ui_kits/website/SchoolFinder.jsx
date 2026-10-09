const { Card, Badge, Button, Tag } = window.KIPPNJMiamiDesignSystem_1916b9;
const { PhotoFrame } = window;

const SCHOOLS = {
  newark: [
    { name: 'KIPP THRIVE Academy', grades: 'K–4', band: 'Elementary', tone: 'blue', seats: 'Now enrolling' },
    { name: 'KIPP Seek Academy', grades: 'K–4', band: 'Elementary', tone: 'blue', seats: 'Now enrolling' },
    { name: 'KIPP Rise Academy', grades: '5–8', band: 'Middle', tone: 'green', seats: 'Waitlist' },
    { name: 'KIPP Newark Collegiate', grades: '9–12', band: 'High', tone: 'orange', seats: 'Now enrolling' },
  ],
  camden: [
    { name: 'KIPP Whittier Elementary', grades: 'K–4', band: 'Elementary', tone: 'blue', seats: 'Now enrolling' },
    { name: 'KIPP Lanning Square', grades: 'K–4', band: 'Elementary', tone: 'blue', seats: 'Now enrolling' },
    { name: 'KIPP Cooper Norcross', grades: '5–8', band: 'Middle', tone: 'green', seats: 'Now enrolling' },
    { name: 'KIPP Camden Collegiate', grades: '9–12', band: 'High', tone: 'orange', seats: 'Waitlist' },
  ],
  paterson: [
    { name: 'KIPP Vista Academy', grades: 'K–4', band: 'Elementary', tone: 'blue', seats: 'Now enrolling' },
    { name: 'KIPP Paterson Prep', grades: '5–8', band: 'Middle', tone: 'green', seats: 'Now enrolling' },
    { name: 'KIPP Paterson Collegiate', grades: '9–12', band: 'High', tone: 'orange', seats: 'Now enrolling' },
  ],
  miami: [
    { name: 'KIPP Sunrise Academy', grades: 'K–4', band: 'Elementary', tone: 'blue', seats: 'Now enrolling' },
    { name: 'KIPP Liberty Academy', grades: 'K–4', band: 'Elementary', tone: 'blue', seats: 'Now enrolling' },
    { name: 'KIPP Miami Prep', grades: '5–8', band: 'Middle', tone: 'green', seats: 'Now enrolling' },
  ],
};

const FILTERS = ['All', 'Elementary', 'Middle', 'High'];

function SchoolFinder({ region }) {
  const [filter, setFilter] = React.useState('All');
  const schools = (SCHOOLS[region] || []).filter((s) => filter === 'All' || s.band === filter);
  const regionName = { newark: 'Newark', camden: 'Camden', paterson: 'Paterson', miami: 'Miami' }[region];

  return (
    <section style={{ background: 'var(--surface-page)' }}>
      <div style={{ maxWidth: 'var(--container-max)', margin: '0 auto', padding: 'var(--space-20) var(--space-8)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 'var(--space-8)', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <span className="kf-eyebrow">Find a school</span>
            <h2 style={{ fontFamily: 'var(--font-brand)', fontWeight: 800, fontSize: 40, letterSpacing: '-.01em', margin: '8px 0 0', color: 'var(--text-strong)' }}>
              Schools in {regionName}
            </h2>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {FILTERS.map((f) => (
              <Tag key={f} selectable selected={filter === f} onClick={() => setFilter(f)}>{f}</Tag>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 'var(--space-6)' }}>
          {schools.map((s) => (
            <Card key={s.name} pad={false} elevation="sm" interactive>
              <PhotoFrame label={s.band} ratio="16 / 9" tone={s.tone} />
              <div style={{ padding: 'var(--space-5)' }}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                  <Badge tone="indigo">{s.grades}</Badge>
                  <Badge tone={s.seats === 'Waitlist' ? 'warning' : 'success'} dot>{s.seats}</Badge>
                </div>
                <h3 style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 19, color: 'var(--text-strong)', lineHeight: 1.15 }}>{s.name}</h3>
                <a href="#" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 12, fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 12, textTransform: 'uppercase', letterSpacing: '.04em', color: 'var(--text-link)' }}>
                  School details
                  <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M6 4l4 4-4 4"/></svg>
                </a>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}

window.SchoolFinder = SchoolFinder;
