const { Card } = window.KIPPNJMiamiDesignSystem_1916b9;

// ---- Grouped bar chart: proficiency by grade band ----
function BarChart() {
  const data = [
    { label: 'Grade 3', kipp: 64, district: 41 },
    { label: 'Grade 4', kipp: 71, district: 45 },
    { label: 'Grade 5', kipp: 68, district: 43 },
    { label: 'Grade 6', kipp: 75, district: 47 },
    { label: 'Grade 7', kipp: 79, district: 49 },
    { label: 'Grade 8', kipp: 82, district: 51 },
  ];
  return (
    <Card elevation="sm">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 18 }}>
        <div>
          <span className="kf-eyebrow">ELA proficiency</span>
          <h3 style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 18, color: 'var(--text-strong)', marginTop: 4 }}>% meeting / exceeding by grade</h3>
        </div>
        <div style={{ display: 'flex', gap: 16 }}>
          <Legend color="var(--viz-1)" label="KIPP" />
          <Legend color="var(--neutral-300)" label="District avg" />
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 18, height: 200, paddingTop: 10 }}>
        {data.map((d) => (
          <div key={d.label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 5, height: 168, width: '100%', justifyContent: 'center' }}>
              <Bar pct={d.kipp} color="var(--viz-1)" />
              <Bar pct={d.district} color="var(--neutral-300)" />
            </div>
            <span style={{ fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)' }}>{d.label}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function Bar({ pct, color }) {
  return (
    <div style={{ width: 18, height: `${pct}%`, background: color, borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0', position: 'relative' }}>
      <span style={{ position: 'absolute', top: -17, left: '50%', transform: 'translateX(-50%)', fontFamily: 'var(--font-mono)', fontSize: 10.5, fontWeight: 700, color: 'var(--text-muted)' }}>{pct}</span>
    </div>
  );
}

function Legend({ color, label }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--text-muted)' }}>
      <span style={{ width: 11, height: 11, borderRadius: 3, background: color }} />{label}
    </span>
  );
}

// ---- Donut: enrollment by grade band ----
function Donut() {
  const segs = [
    { label: 'Elementary', value: 42, color: 'var(--viz-1)' },
    { label: 'Middle', value: 34, color: 'var(--viz-2)' },
    { label: 'High', value: 24, color: 'var(--viz-3)' },
  ];
  let acc = 0;
  const stops = segs.map((s) => { const start = acc; acc += s.value; return `${s.color} ${start}% ${acc}%`; }).join(', ');
  return (
    <Card elevation="sm">
      <span className="kf-eyebrow">Enrollment mix</span>
      <h3 style={{ fontFamily: 'var(--font-brand)', fontWeight: 700, fontSize: 18, color: 'var(--text-strong)', marginTop: 4, marginBottom: 18 }}>Students by grade band</h3>
      <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <div style={{ width: 130, height: 130, borderRadius: '50%', flex: 'none', background: `conic-gradient(${stops})`, position: 'relative' }}>
          <div style={{ position: 'absolute', inset: 26, background: 'var(--surface-card)', borderRadius: '50%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 22, color: 'var(--text-strong)' }}>9.0k</span>
            <span style={{ fontFamily: 'var(--font-sans)', fontSize: 10.5, color: 'var(--text-muted)' }}>students</span>
          </div>
        </div>
        <div style={{ display: 'grid', gap: 10, flex: 1 }}>
          {segs.map((s) => (
            <div key={s.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontFamily: 'var(--font-sans)', fontSize: 13.5, color: 'var(--text-body)' }}>
                <span style={{ width: 11, height: 11, borderRadius: 3, background: s.color }} />{s.label}
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 14, color: 'var(--text-strong)' }}>{s.value}%</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

window.BarChart = BarChart;
window.Donut = Donut;
