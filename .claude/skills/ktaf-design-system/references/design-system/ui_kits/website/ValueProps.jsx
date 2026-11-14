const { PhotoFrame } = window;

const VALUES = [
  { t: 'Promises to children are sacred', d: 'We do what we say. Every child can and will learn at the highest level.' },
  { t: 'Outstanding TEAMmates are everything', d: 'Great schools are built by great people who support one another.' },
  { t: 'Our kids run to school', d: 'Joyful, rigorous classrooms where students love to learn.' },
  { t: 'Our kids will change the world', d: 'To and through college — and into lives of choice and opportunity.' },
];

function ValueProps() {
  return (
    <section style={{ background: 'var(--surface-card)' }}>
      <div style={{
        maxWidth: 'var(--container-max)', margin: '0 auto', padding: 'var(--space-20) var(--space-8)',
        display: 'grid', gridTemplateColumns: '.9fr 1.1fr', gap: 'var(--space-16)', alignItems: 'center',
      }}>
        <div>
          <PhotoFrame label="Classroom" ratio="4 / 5" tone="orange" style={{ boxShadow: 'var(--shadow-lg)' }} />
        </div>
        <div>
          <span className="kf-eyebrow">The Heartbeat</span>
          <h2 style={{ fontFamily: 'var(--font-brand)', fontWeight: 800, fontSize: 40, letterSpacing: '-.01em', margin: '8px 0 var(--space-8)', color: 'var(--text-strong)' }}>
            What we believe
          </h2>
          <div style={{ display: 'grid', gap: 'var(--space-5)' }}>
            {VALUES.map((v, i) => (
              <div key={v.t} style={{ display: 'flex', gap: 'var(--space-4)' }}>
                <div style={{
                  flex: 'none', width: 38, height: 38, borderRadius: 'var(--radius-md)',
                  background: 'var(--brand-accent)', color: 'var(--brand-on-accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 16,
                }}>{i + 1}</div>
                <div>
                  <h3 style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 18, color: 'var(--text-strong)' }}>{v.t}</h3>
                  <p style={{ fontFamily: 'var(--font-sans)', fontSize: 15, lineHeight: 1.5, color: 'var(--text-muted)', marginTop: 3 }}>{v.d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

window.ValueProps = ValueProps;
