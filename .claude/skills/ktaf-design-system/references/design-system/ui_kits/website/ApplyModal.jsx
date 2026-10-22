const { Input, Select, Button } = window.KIPPNJMiamiDesignSystem_1916b9;

function ApplyModal({ region, onClose }) {
  const [done, setDone] = React.useState(false);
  const regionName = { newark: 'Newark', camden: 'Camden', paterson: 'Paterson', miami: 'Miami' }[region];
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,18,60,.55)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
    }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: 'min(520px, 100%)', background: '#fff', borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-xl)', overflow: 'hidden',
      }}>
        <div style={{ background: 'var(--kipp-indigo)', padding: 'var(--space-6)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: '.1em', color: 'var(--brand-accent)' }}>KIPP {regionName}</span>
            <h2 style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 22, color: '#fff', marginTop: 4 }}>Start your application</h2>
          </div>
          <button onClick={onClose} aria-label="Close" style={{ background: 'rgba(255,255,255,.12)', border: 'none', color: '#fff', width: 36, height: 36, borderRadius: 'var(--radius-md)', cursor: 'pointer', fontSize: 18 }}>×</button>
        </div>

        {done ? (
          <div style={{ padding: 'var(--space-12) var(--space-8)', textAlign: 'center' }}>
            <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--status-success-surface)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
              <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="var(--green-700)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 13l4 4L19 7"/></svg>
            </div>
            <h3 style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 22, color: 'var(--text-strong)' }}>You're all set!</h3>
            <p style={{ fontFamily: 'var(--font-sans)', fontSize: 15, color: 'var(--text-muted)', marginTop: 8, maxWidth: '34ch', marginInline: 'auto' }}>
              Our enrollment team will reach out within two business days to finish your {regionName} application.
            </p>
            <div style={{ marginTop: 24 }}><Button variant="accent" onClick={onClose}>Done</Button></div>
          </div>
        ) : (
          <form style={{ padding: 'var(--space-6)', display: 'grid', gap: 'var(--space-4)' }} onSubmit={(e) => { e.preventDefault(); setDone(true); }}>
            <Input label="Parent / guardian name" placeholder="Full name" required />
            <Input label="Email" type="email" placeholder="you@email.com" required />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
              <Select label="Student grade" placeholder="Select grade" options={['Pre-K', 'Kindergarten', 'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8', 'Grade 9']} />
              <Input label="ZIP code" placeholder="07102" required />
            </div>
            <Button type="submit" variant="accent" size="lg" block>Submit application</Button>
            <p style={{ fontFamily: 'var(--font-sans)', fontSize: 12.5, color: 'var(--text-subtle)', textAlign: 'center' }}>
              Free to apply. No test required.
            </p>
          </form>
        )}
      </div>
    </div>
  );
}

window.ApplyModal = ApplyModal;
