const { PhotoFrame } = window;

function Hero({ region, onApply }) {
  const regionName = { newark: 'Newark', camden: 'Camden', paterson: 'Paterson', miami: 'Miami' }[region];
  return (
    <section style={{ background: 'var(--kipp-indigo)', color: '#fff', overflow: 'hidden' }}>
      <div style={{
        maxWidth: 'var(--container-max)', margin: '0 auto', padding: 'var(--space-20) var(--space-8)',
        display: 'grid', gridTemplateColumns: '1.05fr .95fr', gap: 'var(--space-16)', alignItems: 'center',
      }}>
        <div>
          <span style={{
            fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 13,
            textTransform: 'uppercase', letterSpacing: '.12em', color: 'var(--brand-accent)',
          }}>KIPP {regionName} Public Schools</span>
          <h1 style={{
            fontFamily: 'var(--font-brand)', fontWeight: 800, fontSize: 58, lineHeight: 1.02,
            letterSpacing: '-.02em', margin: '16px 0 0', color: '#fff', textWrap: 'balance',
          }}>Our kids will<br/>change the world</h1>
          <p style={{
            fontFamily: 'var(--font-sans)', fontSize: 19, lineHeight: 1.55, color: 'var(--indigo-100)',
            margin: '20px 0 0', maxWidth: '46ch',
          }}>
            Free, public charter schools preparing students in {regionName} for success
            in college, career, and life — to and through.
          </p>
          <div style={{ display: 'flex', gap: 'var(--space-3)', marginTop: 'var(--space-8)' }}>
            <button onClick={onApply} style={{
              background: 'var(--brand-accent)', color: 'var(--brand-on-accent)', border: 'none',
              borderRadius: 'var(--radius-md)', padding: '15px 30px', cursor: 'pointer',
              fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 15,
              textTransform: 'uppercase', letterSpacing: '.04em',
            }}>Enroll your child</button>
            <button style={{
              background: 'transparent', color: '#fff', border: '2px solid rgba(255,255,255,.4)',
              borderRadius: 'var(--radius-md)', padding: '13px 28px', cursor: 'pointer',
              fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 15,
              textTransform: 'uppercase', letterSpacing: '.04em',
            }}>Find a school</button>
          </div>
        </div>

        <div style={{ position: 'relative' }}>
          <PhotoFrame label="Students" ratio="4 / 3.4" tone="blue" style={{ boxShadow: 'var(--shadow-xl)' }} />
          <div style={{
            position: 'absolute', bottom: -22, left: -22, background: 'var(--brand-accent)',
            color: 'var(--brand-on-accent)', padding: '16px 22px', borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
          }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 34, lineHeight: 1 }}>95%</div>
            <div style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: '.06em', marginTop: 4 }}>go to college</div>
          </div>
        </div>
      </div>
    </section>
  );
}

window.Hero = Hero;
