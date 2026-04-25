import { useState, useEffect, useCallback } from "react";
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { API_BASE } from "./AuthContext";
import "./OutcomesDashboard.css";

const ESI_COLORS = { ESI1: "#dc2626", ESI2: "#ea580c", ESI3: "#ca8a04", ESI4: "#16a34a", ESI5: "#6b7280" };
const CARE_COLORS = {
  "CALL_911": "#dc2626", "ED_NOW": "#ea580c", "ED_SOON": "#f97316",
  "URGENT_CARE": "#eab308", "TELEHEALTH": "#0d9488", "PRIMARY_CARE": "#16a34a", "SELF_CARE": "#6b7280",
};

const fmt = (n) => n?.toLocaleString() ?? "—";

// ── Custom tooltip ────────────────────────────────────────────────────────────
function DarkTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <div className="tooltip-label">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="tooltip-row" style={{ color: p.color }}>
          <span>{p.name}:</span> <strong>{fmt(p.value)}{p.name?.includes("pct") || p.name?.includes("%") ? "%" : ""}</strong>
        </div>
      ))}
    </div>
  );
}

// ── KPI card ──────────────────────────────────────────────────────────────────
function KPICard({ label, value, unit = "", sub, color = "#0d9488", benchmark }) {
  return (
    <div className="kpi-card">
      <div className="kpi-value" style={{ color }}>{value}<span className="kpi-unit">{unit}</span></div>
      <div className="kpi-label">{label}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
      {benchmark && <div className="kpi-benchmark">National avg: {benchmark}</div>}
    </div>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────
function Section({ title, subtitle, children, action }) {
  return (
    <div className="dash-section">
      <div className="dash-section-header">
        <div>
          <h3 className="dash-section-title">{title}</h3>
          {subtitle && <p className="dash-section-sub">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

// ── Benchmark comparison row ──────────────────────────────────────────────────
function BenchmarkRow({ metric, yours, national, unit, lower_is_better }) {
  const better = lower_is_better ? yours < national : yours > national;
  const improvement = lower_is_better
    ? Math.round((1 - yours / national) * 100)
    : Math.round((yours / national - 1) * 100);
  const barPct = lower_is_better
    ? Math.min(100, (national / Math.max(yours, 0.1)) * 50)
    : Math.min(100, (yours / Math.max(national, 0.1)) * 50);

  return (
    <div className="benchmark-row">
      <div className="bench-metric">{metric}</div>
      <div className="bench-bars">
        <div className="bench-bar-wrap">
          <div className="bench-bar-label yours">Yours</div>
          <div className="bench-track">
            <div className="bench-fill yours" style={{ width: `${Math.min(100, barPct * 1.2)}%`, background: better ? "#0d9488" : "#dc2626" }} />
          </div>
          <div className="bench-val" style={{ color: better ? "#4ade80" : "#f87171" }}>
            {yours}{unit}
          </div>
        </div>
        <div className="bench-bar-wrap">
          <div className="bench-bar-label national">National</div>
          <div className="bench-track">
            <div className="bench-fill national" style={{ width: `${Math.min(100, barPct)}%` }} />
          </div>
          <div className="bench-val national-val">{national}{unit}</div>
        </div>
      </div>
      <div className={`bench-delta ${better ? "good" : "bad"}`}>
        {better ? "↑" : "↓"} {Math.abs(improvement)}% {better ? "better" : "worse"}
      </div>
    </div>
  );
}

// ── Funnel chart (custom) ─────────────────────────────────────────────────────
function FunnelChart({ data }) {
  const max = data[0]?.count || 1;
  return (
    <div className="funnel-chart">
      {data.map((stage, i) => {
        const w = Math.max(20, (stage.count / max) * 100);
        const colors = ["#0d9488", "#0284c7", "#7c3aed", "#ca8a04", "#16a34a"];
        return (
          <div key={stage.stage} className="funnel-stage">
            <div className="funnel-bar-wrap">
              <div className="funnel-bar" style={{ width: `${w}%`, background: colors[i % colors.length] }}>
                <span className="funnel-count">{fmt(stage.count)}</span>
              </div>
            </div>
            <div className="funnel-label">
              <span>{stage.stage}</span>
              <span className="funnel-pct">{stage.pct}%</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Sepsis component bars ─────────────────────────────────────────────────────
function SepsisComponents({ components }) {
  return (
    <div className="sepsis-components">
      {components.map((c) => (
        <div key={c.name} className="sepsis-comp-row">
          <div className="sepsis-comp-name">{c.name}</div>
          <div className="sepsis-comp-bars">
            <div className="sepsis-track">
              <div className="sepsis-fill" style={{ width: `${c.pct}%`, background: c.pct >= 90 ? "#0d9488" : c.pct >= 80 ? "#ca8a04" : "#dc2626" }} />
            </div>
            <div className="sepsis-val">{c.pct}%</div>
            <div className="sepsis-bench">vs {c.benchmark}%</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── CSV export helper ─────────────────────────────────────────────────────────
function exportCSV(data) {
  const { trends_7d, esi_trends, timeseries } = data;

  const rows = [["Report", "MediScan Gateway — Outcomes Export"], ["Generated", new Date().toISOString()], []];

  rows.push(["--- 7-Day Volume Trends ---"]);
  rows.push(["Date", "Patients", "Avg Wait (min)", "Avg LOS (min)", "LWBS Rate (%)"]);
  (trends_7d || []).forEach(r => rows.push([r.date, r.patients, r.avg_wait_min, r.avg_los_min, r.lwbs_rate]));

  rows.push([]);
  rows.push(["--- 7-Day ESI Distribution ---"]);
  rows.push(["Date", "ESI1", "ESI2", "ESI3", "ESI4", "ESI5"]);
  (esi_trends || []).forEach(r => rows.push([r.date, r.ESI1, r.ESI2, r.ESI3, r.ESI4, r.ESI5]));

  rows.push([]);
  rows.push(["--- 24h Hourly Volume ---"]);
  rows.push(["Time", "Patients", "Wait (min)"]);
  (timeseries || []).forEach(r => rows.push([r.time, r.patients, r.wait_min]));

  const csv = rows.map(r => r.map(v => `"${v ?? ""}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `mediscan-outcomes-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Satisfaction card ─────────────────────────────────────────────────────────
function SatisfactionSection({ user }) {
  const [sat, setSat] = useState(null);
  useEffect(() => {
    fetch(`${API_BASE}/outcomes/satisfaction`, {
      headers: { Authorization: `Bearer ${user?.token}` },
    }).then(r => r.ok ? r.json() : null).then(setSat).catch(() => {});
  }, [user?.token]);

  if (!sat || sat.total_responses === 0) {
    return (
      <Section title="Patient Satisfaction" subtitle="Post-discharge feedback scores">
        <div style={{ textAlign: "center", color: "#475569", padding: "32px 0", fontSize: 14 }}>
          No feedback collected yet — feedback is submitted via the patient portal after discharge.
        </div>
      </Section>
    );
  }

  const stars = Array.from({ length: 5 }, (_, i) => i + 1);
  const maxDist = Math.max(...Object.values(sat.distribution));

  return (
    <Section title="Patient Satisfaction" subtitle={`${sat.total_responses} responses · avg ${sat.avg_rating}/5`}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <div>
          <div style={{ fontSize: 48, fontWeight: 800, color: "#0d9488", lineHeight: 1 }}>{sat.avg_rating}</div>
          <div style={{ color: "#64748b", fontSize: 13, marginBottom: 16 }}>out of 5 · {sat.total_responses} responses</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {stars.reverse().map(s => (
              <div key={s} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 12, color: "#64748b", width: 16 }}>{s}★</span>
                <div style={{ flex: 1, height: 8, borderRadius: 4, background: "#1e293b", overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: 4, background: "#0d9488",
                    width: `${Math.round((sat.distribution[String(s)] || 0) / maxDist * 100)}%`,
                    transition: "width 0.4s",
                  }} />
                </div>
                <span style={{ fontSize: 12, color: "#94a3b8", width: 24 }}>{sat.distribution[String(s)] || 0}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600, marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.05em" }}>By Category</div>
          {Object.entries(sat.by_category).map(([cat, avg]) => (
            <div key={cat} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: "1px solid #1e293b" }}>
              <span style={{ fontSize: 13, color: "#94a3b8", textTransform: "capitalize" }}>{cat.replace("_", " ")}</span>
              <span style={{ fontWeight: 700, color: avg >= 4 ? "#4ade80" : avg >= 3 ? "#fbbf24" : "#f87171" }}>{avg}/5</span>
            </div>
          ))}
          {sat.recent_comments?.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>Recent Comments</div>
              {sat.recent_comments.slice(0, 3).map((c, i) => (
                <div key={i} style={{ padding: "8px 10px", background: "#0a1520", borderRadius: 8, marginBottom: 6, fontSize: 12, color: "#94a3b8", borderLeft: `3px solid ${c.rating >= 4 ? "#0d9488" : "#ca8a04"}` }}>
                  <span style={{ color: c.rating >= 4 ? "#4ade80" : "#fbbf24" }}>{"★".repeat(c.rating)}</span>
                  {" "}{c.comment || <i>No comment</i>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Section>
  );
}

// ── Main dashboard ────────────────────────────────────────────────────────────
export default function OutcomesDashboard({ user }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/analytics`, {
        headers: { Authorization: `Bearer ${user?.token}` },
      });
      const json = await res.json();
      setData(json);
      setLastRefresh(new Date());
    } catch (e) {
      console.error("Analytics fetch error:", e);
    } finally {
      setLoading(false);
    }
  }, [user?.token]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="dash-loading">
        <div className="dash-spinner" />
        <span>Loading outcomes data…</span>
      </div>
    );
  }
  if (!data) return <div className="dash-loading">No data available.</div>;

  const { queue: q, performance: perf, timeseries, trends_7d,
          esi_trends, journeys, diversion, sepsis, benchmarks, totals, alerts } = data;

  return (
    <div className="outcomes-dashboard">
      {/* ── Alert strip ── */}
      {alerts?.length > 0 && (
        <div className="alert-strip">
          {alerts.map((a, i) => (
            <div key={i} className={`alert-item alert-${a.level}`}>
              {a.level === "critical" ? "🚨" : a.level === "warning" ? "⚠️" : "ℹ️"} {a.message}
            </div>
          ))}
        </div>
      )}

      {/* ── Top toolbar ── */}
      <div className="dash-toolbar">
        <div className="dash-toolbar-left">
          <span className="dash-title">Command Dashboard</span>
          {lastRefresh && (
            <span className="dash-refresh">Updated {lastRefresh.toLocaleTimeString()}</span>
          )}
        </div>
        <div className="dash-toolbar-right">
          <button className="dash-export-btn" onClick={() => exportCSV(data)}>
            ↓ Export CSV
          </button>
          <button className="dash-export-btn" onClick={() => window.open(`${API_BASE}/report?format=pdf&token=${user?.token}`, "_blank")}>
            ↓ Export PDF
          </button>
        </div>
      </div>

      {/* ── KPI hero row ── */}
      <div className="kpi-grid">
        <KPICard label="Door-to-Triage"    value={`${perf.door_to_triage_seconds}s`}         color="#0d9488"  sub="vs 28 min national avg"       />
        <KPICard label="LWBS Rate"          value={`${perf.lwbs_rate_today}%`}                 color="#22c55e"  sub="vs 5.1% national avg"         />
        <KPICard label="Avg Wait"           value={`${perf.avg_wait_minutes} min`}              color="#0284c7"  sub="vs 99 min national avg"       />
        <KPICard label="ED Diversion Rate"  value={`${diversion.diversion_rate_pct}%`}          color="#7c3aed"  sub="patients routed to lower acuity"/>
        <KPICard label="Sepsis Compliance"  value={`${sepsis.compliance_rate_pct}%`}            color="#f97316"  sub="vs 62% national avg"          />
        <KPICard label="Patients Triaged"   value={fmt(totals?.all_time_scans)}                 color="#94a3b8"  sub="all time"                     />
      </div>

      {/* ── Charts row 1: Volume + ESI breakdown ── */}
      <div className="dash-row-2">
        {/* 24h volume area chart */}
        <Section title="Patient Volume — Last 24h" subtitle="Hourly arrivals and wait times">
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={timeseries} margin={{ top: 4, right: 16, bottom: 0, left: -10 }}>
              <defs>
                <linearGradient id="gradPat" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#0d9488" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#0d9488" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gradWait" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#0284c7" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#0284c7" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" tick={{ fill: "#475569", fontSize: 10 }} interval={3} />
              <YAxis tick={{ fill: "#475569", fontSize: 10 }} />
              <Tooltip content={<DarkTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11, color: "#64748b" }} />
              <Area type="monotone" dataKey="patients"  name="Patients" stroke="#0d9488" fill="url(#gradPat)"  strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="wait_min"  name="Wait (min)" stroke="#0284c7" fill="url(#gradWait)" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
            </AreaChart>
          </ResponsiveContainer>
        </Section>

        {/* ESI distribution donut */}
        <Section title="Current ESI Mix" subtitle="Active queue breakdown">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={[1,2,3,4,5].map(e => ({
                  name: `ESI ${e}`,
                  value: q.esi_breakdown?.[String(e)] || 0,
                }))}
                cx="50%" cy="50%" innerRadius={55} outerRadius={90}
                dataKey="value" paddingAngle={3}
              >
                {[1,2,3,4,5].map(e => (
                  <Cell key={e} fill={Object.values(ESI_COLORS)[e - 1]} />
                ))}
              </Pie>
              <Tooltip content={<DarkTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11, color: "#64748b" }} />
            </PieChart>
          </ResponsiveContainer>
        </Section>
      </div>

      {/* ── Charts row 2: 7-day trends + ESI stacked ── */}
      <div className="dash-row-2">
        <Section title="7-Day Patient Volume" subtitle="Daily arrivals vs LWBS rate">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={trends_7d} margin={{ top: 4, right: 16, bottom: 0, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 11 }} />
              <YAxis tick={{ fill: "#475569", fontSize: 10 }} />
              <Tooltip content={<DarkTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11, color: "#64748b" }} />
              <Bar dataKey="patients" name="Patients" fill="#0d9488" radius={[3,3,0,0]} />
              <Bar dataKey="avg_wait_min" name="Avg Wait (min)" fill="#0284c7" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </Section>

        <Section title="ESI Distribution — 7 Days" subtitle="Acuity mix trend">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={esi_trends} margin={{ top: 4, right: 16, bottom: 0, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 11 }} />
              <YAxis tick={{ fill: "#475569", fontSize: 10 }} />
              <Tooltip content={<DarkTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11, color: "#64748b" }} />
              {["ESI1","ESI2","ESI3","ESI4","ESI5"].map(k => (
                <Bar key={k} dataKey={k} name={k} stackId="a" fill={ESI_COLORS[k]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </Section>
      </div>

      {/* ── CareNavigator diversion ── */}
      <div className="dash-row-2">
        <Section
          title="CareNavigator Diversion"
          subtitle={`${fmt(diversion.total_assessments)} assessments · ${diversion.diversion_rate_pct}% diverted from ED · Est. $${fmt(diversion.estimated_ed_cost_saved)} saved`}
        >
          <div className="diversion-content">
            <ResponsiveContainer width="50%" height={200}>
              <PieChart>
                <Pie
                  data={diversion.breakdown}
                  cx="50%" cy="50%"
                  innerRadius={50} outerRadius={80}
                  dataKey="count" nameKey="label" paddingAngle={2}
                >
                  {diversion.breakdown.map((b, i) => (
                    <Cell key={i} fill={CARE_COLORS[b.level] || "#6b7280"} />
                  ))}
                </Pie>
                <Tooltip content={<DarkTooltip />} />
              </PieChart>
            </ResponsiveContainer>

            <div className="diversion-legend">
              {diversion.breakdown.map((b) => (
                <div key={b.level} className="div-legend-row">
                  <span className="div-dot" style={{ background: CARE_COLORS[b.level] }} />
                  <span className="div-label">{b.label}</span>
                  <span className="div-count">{b.count}</span>
                  <span className="div-pct">{Math.round(b.count / diversion.total_assessments * 100)}%</span>
                </div>
              ))}
            </div>
          </div>
        </Section>

        {/* ── Clinical journeys funnel ── */}
        <Section
          title="Clinical Journeys™"
          subtitle={`${journeys.completion_rate_pct}% completion · ${journeys.escalation_rate_pct}% escalation · ${fmt(journeys.readmissions_averted)} readmissions averted`}
        >
          <div className="journey-kpi-row">
            {[
              ["Completion", `${journeys.completion_rate_pct}%`, "#22c55e"],
              ["Escalation", `${journeys.escalation_rate_pct}%`, "#f97316"],
              ["Readmissions Averted", fmt(journeys.readmissions_averted), "#0d9488"],
              ["Cost Saved", `$${fmt(journeys.estimated_cost_savings)}`, "#7c3aed"],
            ].map(([label, val, color]) => (
              <div key={label} className="journey-kpi">
                <div className="journey-kpi-val" style={{ color }}>{val}</div>
                <div className="journey-kpi-label">{label}</div>
              </div>
            ))}
          </div>
          <FunnelChart data={journeys.funnel} />
        </Section>
      </div>

      {/* ── Sepsis compliance ── */}
      <div className="dash-row-2">
        <Section
          title="Sepsis Bundle Compliance"
          subtitle={`${sepsis.compliance_rate_pct}% overall (vs ${sepsis.national_benchmark_pct}% national) · Avg time to bundle: ${sepsis.avg_time_to_bundle_min} min vs ${sepsis.national_avg_time_min} min nationally`}
        >
          <div className="sepsis-header-stats">
            <div className="sepsis-stat">
              <div className="sepsis-stat-val" style={{ color: "#0d9488" }}>{sepsis.compliance_rate_pct}%</div>
              <div className="sepsis-stat-label">Our Compliance</div>
            </div>
            <div className="sepsis-stat">
              <div className="sepsis-stat-val" style={{ color: "#94a3b8" }}>{sepsis.national_benchmark_pct}%</div>
              <div className="sepsis-stat-label">National Avg</div>
            </div>
            <div className="sepsis-stat">
              <div className="sepsis-stat-val" style={{ color: "#0d9488" }}>{sepsis.avg_time_to_bundle_min} min</div>
              <div className="sepsis-stat-label">Time to Bundle</div>
            </div>
            <div className="sepsis-stat">
              <div className="sepsis-stat-val" style={{ color: "#94a3b8" }}>{sepsis.national_avg_time_min} min</div>
              <div className="sepsis-stat-label">National Time</div>
            </div>
          </div>
          <SepsisComponents components={sepsis.components} />
        </Section>

        {/* ── Benchmark comparison ── */}
        <Section title="Performance vs National Benchmarks" subtitle="Head-to-head vs published ED benchmarks">
          <div className="benchmarks-list">
            {benchmarks.map((b) => (
              <BenchmarkRow key={b.metric} {...b} />
            ))}
          </div>
        </Section>
      </div>

      {/* ── Capacity + LOS trends ── */}
      <Section title="Capacity & Length of Stay — 7 Days" subtitle="Occupancy trend and patient throughput">
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={trends_7d} margin={{ top: 4, right: 16, bottom: 0, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 11 }} />
            <YAxis tick={{ fill: "#475569", fontSize: 10 }} />
            <Tooltip content={<DarkTooltip />} />
            <Legend wrapperStyle={{ fontSize: 11, color: "#64748b" }} />
            <Line type="monotone" dataKey="avg_los_min"  name="Avg LOS (min)"   stroke="#f97316" strokeWidth={2} dot={{ r: 3, fill: "#f97316" }} />
            <Line type="monotone" dataKey="avg_wait_min" name="Avg Wait (min)"  stroke="#0284c7" strokeWidth={2} dot={{ r: 3, fill: "#0284c7" }} />
            <Line type="monotone" dataKey="lwbs_rate"    name="LWBS Rate (%)"   stroke="#dc2626" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </Section>

      {/* ── Patient satisfaction ── */}
      <SatisfactionSection user={user} />
    </div>
  );
}
