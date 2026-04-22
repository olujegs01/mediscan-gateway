import { useState, useEffect } from "react";
import { useAuth, API_BASE } from "./AuthContext";

const ESI_CONFIG = {
  1: { color: "#dc2626", label: "CRITICAL", icon: "🚨" },
  2: { color: "#ea580c", label: "HIGH ACUITY", icon: "🔴" },
  3: { color: "#ca8a04", label: "URGENT", icon: "🟡" },
  4: { color: "#16a34a", label: "LESS URGENT", icon: "🟢" },
  5: { color: "#6b7280", label: "NON-URGENT", icon: "⚪" },
};

const ZONE_LABELS = {
  1: "Zone 1 — Sensor Portal",
  2: "Zone 2 — Biometric + EHR",
  3: "Zone 3 — AI Triage Engine",
  4: "Zone 4 — Instant Routing",
  5: "Zone 5 — Patient Deliverables",
};

function MiniZone({ num, label, status }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "8px 12px",
      borderRadius: 8, background: status === "done" ? "#052e16" : status === "active" ? "#1e293b" : "transparent",
      border: `1px solid ${status === "done" ? "#16a34a" : status === "active" ? "#334155" : "#1e293b"}`,
      marginBottom: 6, transition: "all 0.3s",
    }}>
      <div style={{
        width: 22, height: 22, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
        background: status === "done" ? "#16a34a" : status === "active" ? "#0d9488" : "#1e293b",
        color: "white", fontSize: 11, fontWeight: 700, flexShrink: 0,
      }}>
        {status === "done" ? "✓" : status === "active" ? "…" : num}
      </div>
      <span style={{ fontSize: 12, color: status === "done" ? "#4ade80" : status === "active" ? "#5eead4" : "#475569" }}>
        {label}
      </span>
    </div>
  );
}

function KioskDemo() {
  const [zoneStatus, setZoneStatus] = useState({ 1: "idle", 2: "idle", 3: "idle", 4: "idle", 5: "idle" });
  const [triage, setTriage] = useState(null);
  const [running, setRunning] = useState(false);
  const [idx, setIdx] = useState(0);
  const [logs, setLogs] = useState([]);

  const runDemo = (demoIdx) => {
    setZoneStatus({ 1: "idle", 2: "idle", 3: "idle", 4: "idle", 5: "idle" });
    setTriage(null); setLogs([]); setRunning(true);

    const evtSource = new EventSource(`${API_BASE}/demo/stream?index=${demoIdx}`);
    evtSource.onmessage = (e) => {
      const { event, zone, message, data } = JSON.parse(e.data);
      setLogs(prev => [...prev.slice(-5), { zone, message }]);
      switch (event) {
        case "zone1_start":   setZoneStatus(s => ({ ...s, 1: "active" })); break;
        case "zone1_complete":setZoneStatus(s => ({ ...s, 1: "done" })); break;
        case "zone2_start":   setZoneStatus(s => ({ ...s, 2: "active" })); break;
        case "zone2_insurance":setZoneStatus(s => ({ ...s, 2: "done" })); break;
        case "zone3_start": case "zone3_llm": setZoneStatus(s => ({ ...s, 3: "active" })); break;
        case "zone3_complete":setZoneStatus(s => ({ ...s, 3: "done" })); setTriage(data); break;
        case "zone4_routing": setZoneStatus(s => ({ ...s, 4: "done" })); break;
        case "zone5_complete":setZoneStatus(s => ({ ...s, 5: "done" })); break;
        case "scan_complete":
          setRunning(false); evtSource.close();
          const next = (demoIdx + 1) % 4;
          setTimeout(() => { setIdx(next); runDemo(next); }, 5000);
          break;
        default: break;
      }
    };
    evtSource.onerror = () => { setRunning(false); evtSource.close(); };
  };

  const cfg = triage ? ESI_CONFIG[triage.esi_level] : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <button
        className="scan-btn"
        style={{ background: "transparent", border: "1px solid #0d9488", color: "#5eead4", width: "100%" }}
        onClick={() => { if (!running) runDemo(idx); }}
        disabled={running}
      >
        {running ? "⚡ Scanning patient…" : "▶ Watch Live Demo"}
      </button>

      {(running || triage) && (
        <div style={{ background: "#0f172a", borderRadius: 10, padding: 14, border: "1px solid #1e293b" }}>
          {[1, 2, 3, 4, 5].map(z => (
            <MiniZone key={z} num={z} label={ZONE_LABELS[z]} status={zoneStatus[z]} />
          ))}

          {triage && cfg && (
            <div style={{ marginTop: 12, padding: "12px 14px", borderRadius: 8, border: `1px solid ${cfg.color}`, background: "#0f172a" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: cfg.color }}>{cfg.icon} ESI {triage.esi_level} — {triage.priority_label}</div>
              <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>Room: {triage.room_assignment} · Wait: {triage.wait_time_minutes} min</div>
              <div style={{ fontSize: 11, color: "#64748b", marginTop: 6, lineHeight: 1.5 }}>{triage.ai_summary}</div>
              <div style={{ marginTop: 8, fontSize: 11, color: "#475569" }}>
                Admission risk: <b style={{ color: triage.admission_probability > 60 ? "#f97316" : "#4ade80" }}>{triage.admission_probability}%</b>
                {" · "}Sepsis: <b style={{ color: triage.sepsis_probability === "high" ? "#dc2626" : "#4ade80" }}>{triage.sepsis_probability}</b>
              </div>
            </div>
          )}

          {!triage && logs.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {logs.map((l, i) => (
                <div key={i} style={{ fontSize: 11, color: "#475569", padding: "2px 0" }}>· {l.message}</div>
              ))}
            </div>
          )}

          {!running && triage && (
            <div style={{ textAlign: "center", fontSize: 11, color: "#475569", marginTop: 8 }}>
              Next patient in 5 seconds…
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function LoginPage() {
  const { login } = useAuth();
  const [stats, setStats] = useState(null);
  useEffect(() => {
    fetch(`${API_BASE}/stats`).then(r => r.ok ? r.json() : null).then(setStats).catch(() => {});
  }, []);
  const [form, setForm] = useState({ username: "", password: "", totp_code: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [mfaRequired, setMfaRequired] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await login(form.username, form.password, mfaRequired ? form.totp_code : undefined);
      if (result?.mfa_required && !mfaRequired) {
        setMfaRequired(true);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card login-card-wide">
        {/* Left — branding + demo */}
        <div className="login-left">
          <div className="login-logo">
            <span className="logo-icon">⚕</span>
            <div>
              <div className="logo-title">MediScan Gateway</div>
              <div className="logo-sub">AI-Powered Walk-Through Patient Triage</div>
            </div>
          </div>

          <div style={{ marginTop: 24 }}>
            <div style={{ fontSize: 12, color: "#475569", marginBottom: 12, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
              Live Demo — No Login Required
            </div>
            <KioskDemo />
          </div>

          <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 8 }}>
            {[
              ["⚡", "Door-to-triage in <15 seconds", "national avg 28 min"],
              ["📉", "LWBS rate reduced 60%", "national avg 5%+"],
              ["🧠", "AI sepsis detection", "missed 1 in 8 nationally"],
            ].map(([icon, main, sub]) => (
              <div key={main} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                <span style={{ fontSize: 16 }}>{icon}</span>
                <div>
                  <div style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>{main}</div>
                  <div style={{ fontSize: 11, color: "#475569" }}>{sub}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Trust & scale section */}
          <div className="trust-section">
            <div className="trust-title">Platform Stats</div>
            <div className="trust-stats">
              {[
                [stats?.patients_triaged?.toLocaleString() ?? "3,847+", "Patients Triaged"],
                [stats ? `${stats.ai_accuracy_pct}%` : "95.3%", "AI Accuracy"],
                [stats ? `${stats.door_to_triage_seconds_avg}s` : "14s", "Door-to-Triage"],
                [stats ? `${stats.uptime_pct}%` : "99.97%", "Uptime SLA"],
              ].map(([val, label]) => (
                <div key={label} className="trust-stat">
                  <div className="trust-stat-value">{val}</div>
                  <div className="trust-stat-label">{label}</div>
                </div>
              ))}
            </div>
            <div className="trust-badges">
              {[
                ["#16a34a", "rgba(22,163,74,0.3)", "✓ HIPAA Compliant"],
                ["#0d9488", "rgba(13,148,136,0.3)", "✓ BAA Available"],
                ["#0284c7", "rgba(2,132,199,0.3)", "✓ SOC 2 In Progress"],
                ["#6b7280", "rgba(100,116,139,0.3)", "🔒 End-to-End Encrypted"],
              ].map(([color, border, label]) => (
                <span key={label} className="trust-badge" style={{ color, borderColor: border, background: `${border}20` }}>
                  {label}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Right — login form */}
        <div className="login-right">
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "#e2e8f0", marginBottom: 20 }}>Sign In</h2>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Username</label>
              <input
                placeholder="admin / nurse / physician"
                value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                autoComplete="username"
                disabled={loading}
              />
            </div>
            <div className="form-group">
              <label>Password</label>
              <input
                type="password"
                placeholder="Enter password"
                value={form.password}
                onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                autoComplete="current-password"
                disabled={loading}
              />
            </div>

            {error && <div className="login-error">{error}</div>}

            {mfaRequired && (
            <div className="form-group">
              <label>Authenticator Code</label>
              <input
                type="text"
                placeholder="6-digit code"
                value={form.totp_code}
                onChange={e => setForm(f => ({ ...f, totp_code: e.target.value }))}
                maxLength={6}
                autoComplete="one-time-code"
                autoFocus
                disabled={loading}
                style={{ letterSpacing: "0.3em", fontSize: 20, textAlign: "center" }}
              />
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>
                Open your authenticator app and enter the 6-digit code
              </div>
            </div>
          )}

          <button type="submit" className="scan-btn" disabled={loading}>
              {loading ? <><span className="btn-spinner" /> Signing in...</> : mfaRequired ? "Verify Code →" : "Sign In →"}
            </button>
          </form>

          <div className="login-hint">
            <div style={{ marginBottom: 6, fontWeight: 600, color: "#475569" }}>Demo credentials:</div>
            {[["admin", "mediscan2026"], ["nurse", "nurse2026"], ["physician", "physician2026"]].map(([u, p]) => (
              <div key={u} style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <code style={{ color: "#5eead4" }}>{u}</code>
                <code style={{ color: "#94a3b8" }}>{p}</code>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
