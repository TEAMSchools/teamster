const { StatCallout } = window.KIPPNJMiamiDesignSystem_1916b9;

const STATS = [
  { value: '9,000+', label: 'Students enrolled' },
  { value: '20', label: 'Schools' },
  { value: '95%', label: 'College enrollment' },
  { value: '4', label: 'Cities' },
];

function StatBand() {
  return (
    <section style={{ background: 'var(--surface-card)', borderBottom: '1px solid var(--border-subtle)' }}>
      <div style={{
        maxWidth: 'var(--container-max)', margin: '0 auto', padding: 'var(--space-16) var(--space-8)',
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-8)',
      }}>
        {STATS.map((s) => (
          <div key={s.label} style={{ textAlign: 'center' }}>
            <StatCallout value={s.value} label={s.label} size="lg" tone="accent" style={{ alignItems: 'center' }} />
          </div>
        ))}
      </div>
    </section>
  );
}

window.StatBand = StatBand;
