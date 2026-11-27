const { Card, Badge, StatCallout } = window.KIPPNJMiamiDesignSystem_1916b9;

const ROWS = [
  { school: 'KIPP Rise Academy', region: 'Newark', band: '5–8', ela: 79, math: 74, att: 94.2, trend: 'up' },
  { school: 'KIPP Newark Collegiate', region: 'Newark', band: '9–12', ela: 71, math: 68, att: 92.8, trend: 'up' },
  { school: 'KIPP Cooper Norcross', region: 'Camden', band: '5–8', ela: 66, math: 70, att: 93.5, trend: 'flat' },
  { school: 'KIPP Paterson Prep', region: 'Paterson', band: '5–8', ela: 72, math: 69, att: 91.4, trend: 'up' },
  { school: 'KIPP Miami Prep', region: 'Miami', band: '5–8', ela: 75, math: 73, att: 95.1, trend: 'up' },
];

const regionTone = { Newark: 'info', Camden: 'success', Paterson: 'danger', Miami: 'warning' };

function DataTable() {
  return (
    <Card elevation="sm" pad={false}>
      <div style={{ padding: '18px var(--space-6) 14px', borderBottom: '1px solid var(--border-subtle)' }}>
        <span className="kf-eyebrow">School comparison</span>
        <h3 style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 18, color: 'var(--text-strong)', marginTop: 4 }}>Performance by school</h3>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['School', 'Region', 'Band', 'ELA', 'Math', 'Attendance', ''].map((h, i) => (
              <th key={h + i} style={{
                textAlign: i > 2 && i < 6 ? 'right' : 'left', padding: '11px var(--space-6)',
                fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 11, textTransform: 'uppercase',
                letterSpacing: '.06em', color: 'var(--text-muted)', background: 'var(--surface-sunken)',
                borderBottom: '1px solid var(--border-subtle)', whiteSpace: 'nowrap',
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => (
            <tr key={r.school} style={{ borderBottom: '1px solid var(--divider)' }}>
              <td style={{ padding: '13px var(--space-6)', fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: 14, color: 'var(--text-strong)' }}>{r.school}</td>
              <td style={{ padding: '13px var(--space-6)' }}><Badge tone={regionTone[r.region]}>{r.region}</Badge></td>
              <td style={{ padding: '13px var(--space-6)', fontFamily: 'var(--font-sans)', fontSize: 13.5, color: 'var(--text-muted)' }}>{r.band}</td>
              <td style={{ padding: '13px var(--space-6)', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 14, color: 'var(--text-strong)' }}>{r.ela}%</td>
              <td style={{ padding: '13px var(--space-6)', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 14, color: 'var(--text-strong)' }}>{r.math}%</td>
              <td style={{ padding: '13px var(--space-6)', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 14, color: 'var(--text-strong)' }}>{r.att}%</td>
              <td style={{ padding: '13px var(--space-6)', textAlign: 'center', width: 40 }}>
                {r.trend === 'up'
                  ? <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="var(--green-700)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M3 11l5-5 5 5" /></svg>
                  : <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="var(--text-subtle)" strokeWidth="2.4" strokeLinecap="round"><path d="M3 8h10" /></svg>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

window.DataTable = DataTable;
