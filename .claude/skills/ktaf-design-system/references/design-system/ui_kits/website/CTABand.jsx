function CTABand({ onApply }) {
  return (
    <section style={{ background: 'var(--brand-accent)' }}>
      <div style={{
        maxWidth: 'var(--container-max)', margin: '0 auto', padding: 'var(--space-16) var(--space-8)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-8)', flexWrap: 'wrap',
      }}>
        <div>
          <h2 style={{ fontFamily: 'var(--font-brand)', fontWeight: 800, fontSize: 36, letterSpacing: '-.01em', color: 'var(--brand-on-accent)', textWrap: 'balance' }}>
            Enrollment is open. Free, public, and close to home.
          </h2>
          <p style={{ fontFamily: 'var(--font-sans)', fontSize: 17, color: 'var(--brand-on-accent)', opacity: .85, marginTop: 8 }}>
            Apply in minutes — no test, no tuition, no catch.
          </p>
        </div>
        <button onClick={onApply} style={{
          background: 'var(--kipp-indigo)', color: '#fff', border: 'none',
          borderRadius: 'var(--radius-md)', padding: '17px 34px', cursor: 'pointer', whiteSpace: 'nowrap',
          fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 16,
          textTransform: 'uppercase', letterSpacing: '.04em',
        }}>Start your application</button>
      </div>
    </section>
  );
}

window.CTABand = CTABand;
