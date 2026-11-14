const { StatCallout, Card } = window.KIPPNJMiamiDesignSystem_1916b9;

function KpiRow() {
  const kpis = [
    { value: '9,042', label: 'Students enrolled', trend: { dir: 'up', text: '+218 YoY' } },
    { value: '93.4%', label: 'Avg daily attendance', trend: { dir: 'up', text: '+1.2 pts' } },
    { value: '74%', label: 'ELA proficiency', trend: { dir: 'up', text: '+5 pts' } },
    { value: '95.2%', label: 'College enrollment', trend: { dir: 'up', text: '+3.1 pts' } },
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-5)' }}>
      {kpis.map((k) => (
        <Card key={k.label} elevation="sm">
          <StatCallout value={k.value} label={k.label} size="md" trend={k.trend} />
        </Card>
      ))}
    </div>
  );
}

function DashBody({ section }) {
  const titles = {
    overview: 'Network overview', academics: 'Academics', attendance: 'Attendance',
    enrollment: 'Enrollment', staff: 'Staff & culture',
  };
  return (
    <main style={{ flex: 1, padding: 'var(--space-8)', background: 'var(--surface-page)', overflow: 'auto' }}>
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <span className="kf-eyebrow">2025–26 school year</span>
        <h1 style={{ fontFamily: 'var(--font-brand)', fontWeight: 800, fontSize: 32, letterSpacing: '-.01em', color: 'var(--text-strong)', marginTop: 4 }}>{titles[section]}</h1>
      </div>

      <div style={{ display: 'grid', gap: 'var(--space-6)' }}>
        <KpiRow />
        <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 'var(--space-6)' }}>
          <window.BarChart />
          <window.Donut />
        </div>
        <window.DataTable />
      </div>
    </main>
  );
}

window.DashBody = DashBody;
