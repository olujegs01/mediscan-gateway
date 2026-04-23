import React, { useState, useRef, useEffect, useCallback } from "react";
import "./App.css";
import { useAuth, API_BASE } from "./AuthContext";
import { useWebSocket } from "./hooks/useWebSocket";
import ClinicalJourneys from "./ClinicalJourneys";
import OutcomesDashboard from "./OutcomesDashboard";
import BillingPage from "./BillingPage";

const WS_BASE = API_BASE.replace(/^https/, "wss").replace(/^http/, "ws");

const ESI_CONFIG = {
  1: { color: "#dc2626", bg: "#fef2f2", label: "CRITICAL", icon: "🚨", destination: "Trauma Bay" },
  2: { color: "#ea580c", bg: "#fff7ed", label: "HIGH ACUITY", icon: "🔴", destination: "Immediate Bed" },
  3: { color: "#ca8a04", bg: "#fefce8", label: "URGENT", icon: "🟡", destination: "Fast Track" },
  4: { color: "#16a34a", bg: "#f0fdf4", label: "LESS URGENT", icon: "🟢", destination: "Self-Serve Kiosk" },
  5: { color: "#6b7280", bg: "#f9fafb", label: "NON-URGENT", icon: "⚪", destination: "Self-Serve Kiosk" },
};

const ZONE_LABELS = {
  1: "Zone 1 — Walk-through Sensor Portal",
  2: "Zone 2 — Biometric ID + EHR + Insurance",
  3: "Zone 3 — AI Diagnostic Engine",
  4: "Zone 4 — Instant Routing",
  5: "Zone 5 — Patient Deliverables",
};

function SensorPortal({ active }) {
  return (
    <div className={`sensor-portal ${active ? "active" : ""}`}>
      <div className="portal-arch">
        <div className="scan-beam" />
        <div className="patient-silhouette">🧍</div>
      </div>
      <div className="sensor-labels">
        <div className="sensor-pill mmwave">📡 mmWave</div>
        <div className="sensor-pill thermal">🌡 Thermal IR</div>
        <div className="sensor-pill lidar">📐 LiDAR</div>
        <div className="sensor-pill spectral">☢️ Spectral</div>
      </div>
    </div>
  );
}

function ZoneStep({ zoneNum, label, status, children }) {
  const statusClass = status === "active" ? "zone-active" : status === "done" ? "zone-done" : "zone-idle";
  return (
    <div className={`zone-step ${statusClass}`}>
      <div className="zone-header">
        <span className="zone-num">{zoneNum}</span>
        <span className="zone-label">{label}</span>
        {status === "done" && <span className="zone-check">✓</span>}
        {status === "active" && <span className="zone-spinner" />}
      </div>
      {status !== "idle" && children && <div className="zone-body">{children}</div>}
    </div>
  );
}

function SensorCard({ data }) {
  if (!data) return null;
  return (
    <div className="sensor-card">
      <div className="sensor-row">
        <span className="sensor-icon">📡</span>
        <div>
          <div className="sensor-title">mmWave Radar</div>
          <div className="sensor-vals">
            HR: <b>{data.heart_rate} bpm</b> · RR: <b>{data.respiratory_rate}/min</b> · Gait: <b>{data.gait_symmetry}</b>
          </div>
        </div>
      </div>
      <div className="sensor-row">
        <span className="sensor-icon">🌡</span>
        <div>
          <div className="sensor-title">Thermal IR</div>
          <div className="sensor-vals">
            Skin Temp: <b>{data.skin_temp}°C</b>
            {data.fever_flag && <span className="flag fever"> 🔥 FEVER</span>}
            {data.inflammation_zones?.length > 0 && <span className="flag"> · {data.inflammation_zones.join(", ")}</span>}
          </div>
        </div>
      </div>
      <div className="sensor-row">
        <span className="sensor-icon">📐</span>
        <div>
          <div className="sensor-title">LiDAR Depth</div>
          <div className="sensor-vals">
            Posture: <b>{data.posture_score}/100</b>
            {data.limb_asymmetry && <span className="flag warning"> ⚠️ {data.limb_asymmetry}</span>}
            {data.injury_indicators?.length > 0 && <span className="flag warning"> · {data.injury_indicators.join(", ")}</span>}
          </div>
        </div>
      </div>
      {(data.bone_density_flag || data.dense_tissue_alerts?.length > 0) && (
        <div className="sensor-row">
          <span className="sensor-icon">☢️</span>
          <div>
            <div className="sensor-title">Spectral X-ray</div>
            <div className="sensor-vals">
              {data.dense_tissue_alerts?.join(" · ") || "No flags"}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TriageCard({ data }) {
  if (!data) return null;
  const cfg = ESI_CONFIG[data.esi_level] || ESI_CONFIG[5];
  const sepsisCritical = ["high", "critical"].includes(data.sepsis_probability);
  return (
    <div className="triage-card" style={{ borderColor: cfg.color, background: cfg.bg }}>
      <div className="esi-badge" style={{ background: cfg.color }}>
        ESI {data.esi_level} — {cfg.label}
      </div>

      {/* Sepsis alert banner */}
      {sepsisCritical && (
        <div className="sepsis-alert">
          🧬 SEPSIS {data.sepsis_probability?.toUpperCase()} — qSOFA {data.qsofa_score} · SIRS {data.sirs_criteria_met}/4
          {data.sepsis_bundle_triggered && " · BUNDLE TRIGGERED"}
        </div>
      )}

      {/* Behavioral health banner */}
      {data.behavioral_health_flag && (
        <div className="bh-alert">🧠 BEHAVIORAL HEALTH — Crisis routing active</div>
      )}

      <div className="triage-summary">{data.ai_summary || data.primary_concern}</div>

      {/* Clinical scores row */}
      <div className="clinical-scores">
        <div className="score-pill">
          <span className="score-label">Admit Risk</span>
          <span className="score-val" style={{ color: data.admission_probability >= 70 ? "#ef4444" : data.admission_probability >= 40 ? "#f97316" : "#22c55e" }}>
            {data.admission_probability}%
          </span>
        </div>
        <div className="score-pill">
          <span className="score-label">LWBS Risk</span>
          <span className="score-val" style={{ color: data.lwbs_risk === "high" ? "#ef4444" : data.lwbs_risk === "moderate" ? "#f97316" : "#22c55e" }}>
            {data.lwbs_risk}
          </span>
        </div>
        <div className="score-pill">
          <span className="score-label">Disposition</span>
          <span className="score-val">{data.disposition_prediction}</span>
        </div>
        {data.vertical_flow_eligible && (
          <div className="score-pill eligible">⬆ Vertical Flow</div>
        )}
        {data.fast_track_eligible && (
          <div className="score-pill eligible">⚡ Fast Track</div>
        )}
      </div>

      {data.risk_flags?.length > 0 && (
        <div className="risk-flags">
          {data.risk_flags.map((f, i) => (
            <span key={i} className="risk-flag" style={{ borderColor: cfg.color, color: cfg.color }}>⚑ {f}</span>
          ))}
        </div>
      )}

      {data.differential_diagnoses?.length > 0 && (
        <div className="differentials">
          <span className="diff-label">DDx: </span>
          {data.differential_diagnoses.join(" · ")}
        </div>
      )}

      {data.time_sensitive_interventions?.length > 0 && (
        <div className="time-sensitive">
          ⏱ &lt;30min: {data.time_sensitive_interventions.join(" · ")}
        </div>
      )}

      <div className="routing-dest">
        📍 {data.routing_destination} → <b>{data.room_assignment}</b>
      </div>
    </div>
  );
}

function PatientQueueCard({ patient, onDischarge, onSOAP }) {
  const cfg = ESI_CONFIG[patient.esi_level] || ESI_CONFIG[5];
  const td = patient.triage_detail || {};
  const sepsisCritical = ["high", "critical"].includes(td.sepsis_probability);

  return (
    <div className="queue-card" style={{ borderLeftColor: cfg.color }}>
      {sepsisCritical && <div className="card-sepsis-banner">🧬 SEPSIS {td.sepsis_probability?.toUpperCase()} · qSOFA {td.qsofa_score}</div>}
      {td.behavioral_health_flag && <div className="card-bh-banner">🧠 BEHAVIORAL HEALTH</div>}

      <div className="queue-top">
        <div>
          <div className="queue-name">{patient.name}</div>
          <div className="queue-meta">Age {patient.age} · {patient.chief_complaint}</div>
        </div>
        <div className="queue-esi" style={{ background: cfg.color }}>
          {cfg.icon} ESI {patient.esi_level}
        </div>
      </div>

      <div className="queue-details">
        <span>🏥 {patient.room_assignment}</span>
        <span>⏱ ~{patient.wait_time_estimate} min</span>
        <span>🆔 {patient.wristband_code}</span>
      </div>

      {/* Clinical intelligence badges */}
      <div className="queue-intel">
        {td.admission_probability != null && (
          <span className="intel-badge" style={{ color: td.admission_probability >= 70 ? "#ef4444" : "#94a3b8" }}>
            Admit {td.admission_probability}%
          </span>
        )}
        {td.lwbs_risk === "high" && <span className="intel-badge warn">⚠ LWBS Risk</span>}
        {td.vertical_flow_eligible && <span className="intel-badge ok">⬆ Vertical</span>}
        {td.fast_track_eligible && <span className="intel-badge ok">⚡ Fast Track</span>}
        {td.disposition_prediction && <span className="intel-badge">{td.disposition_prediction}</span>}
      </div>

      {patient.risk_flags?.length > 0 && (
        <div className="queue-flags">
          {patient.risk_flags.map((f, i) => (
            <span key={i} className="queue-flag" style={{ background: cfg.bg, color: cfg.color }}>{f}</span>
          ))}
        </div>
      )}

      {td.differential_diagnoses?.length > 0 && (
        <div className="queue-ddx">DDx: {td.differential_diagnoses.join(" · ")}</div>
      )}

      {patient.care_pre_staged?.length > 0 && (
        <div className="queue-orders">
          📋 {patient.care_pre_staged.slice(0, 3).join(" · ")}
          {patient.care_pre_staged.length > 3 && ` +${patient.care_pre_staged.length - 3} more`}
        </div>
      )}

      <div className="queue-card-actions">
        <button className="soap-btn" onClick={() => onSOAP(patient)}>
          📝 SOAP Note
        </button>
        <button className="discharge-btn" onClick={() => onDischarge(patient.patient_id)}>
          Discharge
        </button>
      </div>
    </div>
  );
}

// ── Bed Board ─────────────────────────────────────────────────────────────────

const BED_STATUS_CONFIG = {
  available: { color: "#22c55e", bg: "#052e16", label: "Available" },
  occupied:  { color: "#f97316", bg: "#431407", label: "Occupied" },
  boarding:  { color: "#dc2626", bg: "#450a0a", label: "Boarding" },
  cleaning:  { color: "#94a3b8", bg: "#1e293b", label: "Cleaning" },
};

const STATUS_CYCLE = ["available", "occupied", "boarding", "cleaning"];

function BedBoard({ user }) {
  const [beds, setBeds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(null);

  const fetchBeds = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/beds`, {
        headers: { Authorization: `Bearer ${user?.token}` },
      });
      setBeds(await res.json());
    } catch (e) {
      console.error("Beds fetch error:", e);
    } finally {
      setLoading(false);
    }
  }, [user?.token]);

  useEffect(() => { fetchBeds(); const t = setInterval(fetchBeds, 20000); return () => clearInterval(t); }, [fetchBeds]);

  const cycleStatus = async (bed) => {
    const next = STATUS_CYCLE[(STATUS_CYCLE.indexOf(bed.status) + 1) % STATUS_CYCLE.length];
    setUpdating(bed.room);
    try {
      const res = await fetch(`${API_BASE}/beds/${encodeURIComponent(bed.room)}`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${user?.token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ status: next, patient_id: next === "available" ? null : bed.patient_id }),
      });
      const updated = await res.json();
      setBeds(prev => prev.map(b => b.room === bed.room ? updated : b));
    } catch (e) {
      console.error("Bed update error:", e);
    } finally {
      setUpdating(null);
    }
  };

  const units = [...new Set(beds.map(b => b.unit))];
  const summary = {
    available: beds.filter(b => b.status === "available").length,
    occupied: beds.filter(b => b.status === "occupied").length,
    boarding: beds.filter(b => b.status === "boarding").length,
    cleaning: beds.filter(b => b.status === "cleaning").length,
  };

  if (loading) return <div className="analytics-loading">Loading bed board...</div>;

  return (
    <div className="bedboard-layout">
      <div className="bedboard-header">
        <div>
          <h2>Live Bed Board</h2>
          <p style={{ color: "#94a3b8", marginTop: 4 }}>Click any bed to cycle its status</p>
        </div>
        <div className="bed-summary-pills">
          {Object.entries(summary).map(([status, count]) => (
            <div key={status} className="bed-summary-pill" style={{ color: BED_STATUS_CONFIG[status].color, borderColor: BED_STATUS_CONFIG[status].color }}>
              <span style={{ fontWeight: 700, fontSize: 18 }}>{count}</span>
              <span style={{ fontSize: 11 }}>{BED_STATUS_CONFIG[status].label}</span>
            </div>
          ))}
        </div>
      </div>

      {units.map(unit => (
        <div key={unit} className="bed-unit">
          <div className="bed-unit-title">{unit}</div>
          <div className="bed-grid">
            {beds.filter(b => b.unit === unit).map(bed => {
              const cfg = BED_STATUS_CONFIG[bed.status] || BED_STATUS_CONFIG.available;
              return (
                <button
                  key={bed.room}
                  className={`bed-cell ${updating === bed.room ? "bed-updating" : ""}`}
                  style={{ borderColor: cfg.color, background: cfg.bg, color: cfg.color }}
                  onClick={() => cycleStatus(bed)}
                  title={`${bed.room} — click to change status`}
                >
                  <div className="bed-room">{bed.room}</div>
                  <div className="bed-status-label">{updating === bed.room ? "…" : cfg.label}</div>
                  {bed.patient_id && bed.status !== "available" && (
                    <div className="bed-patient-id">{bed.patient_id.slice(0, 8)}</div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}

      <div style={{ marginTop: 16, fontSize: 12, color: "#475569" }}>
        Occupancy: {beds.length > 0 ? Math.round(((summary.occupied + summary.boarding) / beds.length) * 100) : 0}% — {beds.length} total beds
      </div>
    </div>
  );
}

// ── Demo / Kiosk Mode ─────────────────────────────────────────────────────────

function DemoPlayer({ onClose }) {
  const [scanning, setScanning] = useState(false);
  const [zoneStatus, setZoneStatus] = useState({ 1: "idle", 2: "idle", 3: "idle", 4: "idle", 5: "idle" });
  const [sensorData, setSensorData] = useState(null);
  const [triageData, setTriageData] = useState(null);
  const [zone5Data, setZone5Data] = useState(null); // eslint-disable-line no-unused-vars
  const [logs, setLogs] = useState([]);
  const [scanComplete, setScanComplete] = useState(false);
  const [demoIndex, setDemoIndex] = useState(0);
  const [demoCount] = useState(4);
  const evtRef = useRef(null);

  const DEMO_NAMES = ["James Okonkwo, 58", "Maria Santos, 34", "Derek Williams, 72", "Aisha Patel, 26"];

  const addLog = (zone, message) => {
    const time = new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    setLogs(prev => [...prev, { zone, message, time }]);
  };

  const runDemo = (idx) => {
    if (evtRef.current) evtRef.current.close();
    setZoneStatus({ 1: "idle", 2: "idle", 3: "idle", 4: "idle", 5: "idle" });
    setSensorData(null); setTriageData(null); setZone5Data(null);
    setScanComplete(false); setLogs([]);
    setScanning(true);

    const evtSource = new EventSource(`${API_BASE}/demo/stream?index=${idx}`);
    evtRef.current = evtSource;

    evtSource.onmessage = (e) => {
      const payload = JSON.parse(e.data);
      const { event, zone, message, data } = payload;
      addLog(zone, message);
      switch (event) {
        case "zone1_start": setZoneStatus(s => ({ ...s, 1: "active" })); break;
        case "zone1_complete": setZoneStatus(s => ({ ...s, 1: "done" })); setSensorData(data); break;
        case "zone2_start": setZoneStatus(s => ({ ...s, 2: "active" })); break;
        case "zone2_insurance": setZoneStatus(s => ({ ...s, 2: "done" })); break;
        case "zone3_start": case "zone3_llm": setZoneStatus(s => ({ ...s, 3: "active" })); break;
        case "zone3_complete": setZoneStatus(s => ({ ...s, 3: "done" })); setTriageData(data); break;
        case "zone4_routing": setZoneStatus(s => ({ ...s, 4: "done" })); break;
        case "zone5_complete": setZoneStatus(s => ({ ...s, 5: "done" })); setZone5Data(data); break;
        case "scan_complete":
          setScanComplete(true); setScanning(false); evtSource.close();
          setTimeout(() => { const next = (idx + 1) % demoCount; setDemoIndex(next); runDemo(next); }, 6000);
          break;
        default: break;
      }
    };
    evtSource.onerror = () => { setScanning(false); evtSource.close(); };
  };

  useEffect(() => { runDemo(demoIndex); return () => evtRef.current?.close(); }, []); // eslint-disable-line

  const cfg = triageData ? ESI_CONFIG[triageData.esi_level] : null;

  return (
    <div className="demo-overlay">
      <div className="demo-panel">
        <div className="demo-header">
          <div>
            <div className="demo-title">⚕ MediScan Gateway — Live Demo</div>
            <div className="demo-sub">AI-Powered Walk-Through Patient Intake · Auto-cycling {demoCount} patients</div>
          </div>
          <button className="demo-close" onClick={onClose}>✕ Exit Demo</button>
        </div>

        <div className="demo-body">
          {/* Portal animation */}
          <div className="demo-portal-col">
            <SensorPortal active={scanning} />
            <div className="demo-patient-label">{DEMO_NAMES[demoIndex]}</div>

            {/* Zone steps */}
            {[1, 2, 3, 4, 5].map(z => (
              <ZoneStep key={z} zoneNum={z} label={ZONE_LABELS[z]} status={zoneStatus[z]} />
            ))}
          </div>

          {/* Result */}
          <div className="demo-result-col">
            {triageData && cfg && (
              <div className="complete-banner" style={{ borderColor: cfg.color, background: cfg.bg }}>
                <div className="complete-icon">{cfg.icon}</div>
                <div>
                  <div className="complete-title" style={{ color: cfg.color }}>{triageData.priority_label} — ESI {triageData.esi_level}</div>
                  <div className="complete-sub">Room: {triageData.room_assignment} · Wait: {triageData.wait_time_minutes} min</div>
                </div>
              </div>
            )}

            {triageData && (
              <div className="card" style={{ marginTop: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#e2e8f0", marginBottom: 8 }}>AI Clinical Summary</div>
                <div style={{ fontSize: 13, color: "#94a3b8", lineHeight: 1.6 }}>{triageData.ai_summary}</div>
                {triageData.risk_flags?.length > 0 && (
                  <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {triageData.risk_flags.map((f, i) => (
                      <span key={i} style={{ fontSize: 11, padding: "3px 8px", borderRadius: 10, background: "#1e293b", color: "#f87171", border: "1px solid #dc2626" }}>{f}</span>
                    ))}
                  </div>
                )}
                <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  <div className="metric-card" style={{ padding: 10 }}>
                    <div className="metric-val" style={{ fontSize: 18 }}>{triageData.admission_probability}%</div>
                    <div className="metric-label">Admission Risk</div>
                  </div>
                  <div className="metric-card" style={{ padding: 10 }}>
                    <div className="metric-val" style={{ fontSize: 18, color: triageData.sepsis_probability === "high" ? "#dc2626" : "#22c55e" }}>{triageData.sepsis_probability}</div>
                    <div className="metric-label">Sepsis Probability</div>
                  </div>
                </div>
              </div>
            )}

            {sensorData && !triageData && (
              <SensorCard data={sensorData} />
            )}

            {scanComplete && (
              <div style={{ textAlign: "center", padding: "16px 0", color: "#94a3b8", fontSize: 13 }}>
                Next patient in 6 seconds...
              </div>
            )}

            <div className="demo-log">
              {logs.slice(-8).map((l, i) => (
                <div key={i} style={{ fontSize: 11, color: "#64748b", padding: "2px 0" }}>
                  <span style={{ color: "#475569" }}>{l.time}</span> · {l.message}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="demo-footer">
          <span style={{ color: "#94a3b8" }}>Door-to-triage: <b style={{ color: "#22c55e" }}>&lt;15 seconds</b></span>
          <span style={{ color: "#94a3b8" }}>National avg: <b style={{ color: "#f87171" }}>28 minutes</b></span>
          <span style={{ color: "#94a3b8" }}>LWBS reduction: <b style={{ color: "#22c55e" }}>60%</b></span>
          <span style={{ color: "#94a3b8" }}>LOS reduction: <b style={{ color: "#22c55e" }}>30%</b></span>
        </div>
      </div>
    </div>
  );
}

function AuditLogPanel({ user }) {
  const [logs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAudit = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/audit?limit=200`, {
        headers: { Authorization: `Bearer ${user?.token}` },
      });
      const data = await res.json();
      setAuditLogs(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("Audit fetch error:", e);
    } finally {
      setLoading(false);
    }
  }, [user?.token]);

  useEffect(() => { fetchAudit(); }, [fetchAudit]);

  const ACTION_COLOR = {
    login: "#60a5fa", scan: "#34d399", discharge: "#f87171",
    view_queue: "#94a3b8", view_analytics: "#a78bfa",
    generate_report: "#fbbf24", view_audit: "#94a3b8",
  };

  if (loading) return <div className="analytics-loading">Loading audit log...</div>;

  return (
    <div className="report-layout">
      <div className="report-header">
        <div>
          <h2>HIPAA Audit Log</h2>
          <p style={{ color: "#94a3b8", marginTop: 4 }}>All access to patient data — last 200 events</p>
        </div>
        <button className="refresh-btn" onClick={fetchAudit}>↻ Refresh</button>
      </div>
      <div className="card" style={{ marginTop: 0, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ background: "#1e293b", color: "#94a3b8" }}>
              {["Timestamp", "User", "Role", "Action", "Patient ID", "IP", "Status"].map(h => (
                <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontWeight: 500, whiteSpace: "nowrap" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logs.map((r, i) => (
              <tr key={r.id} style={{ background: i % 2 === 0 ? "#1a2332" : "#151e2d", color: "#cbd5e1" }}>
                <td style={{ padding: "6px 10px", whiteSpace: "nowrap" }}>{new Date(r.timestamp).toLocaleString()}</td>
                <td style={{ padding: "6px 10px" }}>{r.username}</td>
                <td style={{ padding: "6px 10px", color: "#94a3b8" }}>{r.role}</td>
                <td style={{ padding: "6px 10px" }}>
                  <span style={{ color: ACTION_COLOR[r.action] || "#e2e8f0", fontWeight: 600 }}>{r.action}</span>
                </td>
                <td style={{ padding: "6px 10px", color: "#64748b", fontFamily: "monospace", fontSize: 11 }}>
                  {r.patient_id ? r.patient_id.slice(0, 12) + "…" : "—"}
                </td>
                <td style={{ padding: "6px 10px", color: "#475569" }}>{r.ip_address || "—"}</td>
                <td style={{ padding: "6px 10px" }}>
                  <span style={{ color: r.success ? "#4ade80" : "#f87171" }}>{r.success ? "✓" : "✗"}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {logs.length === 0 && (
          <div style={{ textAlign: "center", padding: "40px", color: "#475569" }}>No audit records yet</div>
        )}
      </div>
    </div>
  );
}

function ShiftReportPanel({ user, queue = [] }) {
  const [generating, setGenerating] = useState(false);
  const [emailing, setEmailing] = useState(false);
  const [reports, setReports] = useState([]);
  const [msg, setMsg] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [showEmailInput, setShowEmailInput] = useState(false);

  const loadReports = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/report`, {
        headers: { Authorization: `Bearer ${user?.token}` },
      });
      const data = await res.json();
      setReports(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("Report list error:", e);
    }
  }, [user?.token]);

  useEffect(() => { loadReports(); }, [loadReports]);

  const handleGenerate = async (format) => {
    setGenerating(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/report?format=${format}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${user?.token}` },
      });
      if (format === "pdf") {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `mediscan_shift_report_${new Date().toISOString().slice(0,16).replace("T","_")}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        setMsg("PDF downloaded.");
      } else {
        await res.json();
        setMsg("Report saved.");
      }
      loadReports();
    } catch {
      setMsg("Error generating report.");
    } finally {
      setGenerating(false);
    }
  };

  const handleEmail = async () => {
    setEmailing(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/report/email`, {
        method: "POST",
        headers: { Authorization: `Bearer ${user?.token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ recipient: emailInput || null }),
      });
      const data = await res.json();
      setMsg(data.sent ? `Report emailed to ${data.recipient}.` : "Email failed — check server logs.");
      setShowEmailInput(false);
      setEmailInput("");
    } catch {
      setMsg("Network error sending email.");
    } finally {
      setEmailing(false);
    }
  };

  // Live preview stats from current queue
  const total = queue.length;
  const esiCounts = [1,2,3,4,5].map(e => ({ level: e, count: queue.filter(p => p.esi_level === e).length }));
  const sepsis = queue.filter(p => ["high","critical"].includes(p.triage_detail?.sepsis_probability)).length;
  const bh = queue.filter(p => p.triage_detail?.behavioral_health_flag).length;
  const admissions = queue.filter(p => (p.triage_detail?.admission_probability || 0) >= 60).length;
  const avgWait = total ? Math.round(queue.reduce((s, p) => s + (p.wait_time_estimate || 0), 0) / total) : 0;
  const esiColors = { 1: "#dc2626", 2: "#ea580c", 3: "#ca8a04", 4: "#16a34a", 5: "#6b7280" };

  return (
    <div className="report-layout">
      <div className="report-header">
        <div>
          <h2>Shift Handoff Report</h2>
          <p style={{ color: "#94a3b8", marginTop: 4 }}>HIPAA-compliant PDF for charge nurse handoff</p>
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button className="scan-btn" onClick={() => handleGenerate("pdf")} disabled={generating} style={{ background: "#0d9488" }}>
            {generating ? "Generating…" : "⬇ Download PDF"}
          </button>
          <button className="refresh-btn" onClick={() => handleGenerate("json")} disabled={generating}>
            Save Report
          </button>
          <button className="refresh-btn" onClick={() => setShowEmailInput(v => !v)} style={{ background: "#1e293b" }}>
            ✉ Email Report
          </button>
        </div>
      </div>

      {showEmailInput && (
        <div style={{ display: "flex", gap: 10, marginBottom: 12, alignItems: "center" }}>
          <input
            style={{ flex: 1, padding: "8px 12px", background: "#0f1923", border: "1px solid #1e293b", borderRadius: 8, color: "#e2e8f0", fontSize: 13 }}
            placeholder="Recipient email (leave blank for admin default)"
            value={emailInput}
            onChange={e => setEmailInput(e.target.value)}
          />
          <button className="scan-btn" onClick={handleEmail} disabled={emailing} style={{ background: "#0d9488", whiteSpace: "nowrap" }}>
            {emailing ? "Sending…" : "Send →"}
          </button>
        </div>
      )}

      {msg && <div style={{ padding: "8px 12px", background: "#f0fdf410", color: "#4ade80", borderRadius: 6, marginBottom: 12, fontSize: 13 }}>{msg}</div>}

      {/* Live preview of current shift */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h3 style={{ color: "#e2e8f0", fontSize: 14, fontWeight: 600, margin: 0 }}>Current Shift Preview</h3>
          <span style={{ fontSize: 12, color: "#475569" }}>Live data · {new Date().toLocaleTimeString()}</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 20 }}>
          {[
            ["Total Patients", total, "#0d9488"],
            ["Avg Wait", `${avgWait} min`, "#0284c7"],
            ["Sepsis Alerts", sepsis, sepsis > 0 ? "#dc2626" : "#4ade80"],
            ["BH Patients", bh, "#7c3aed"],
            ["Admissions Predicted", admissions, "#f97316"],
          ].map(([label, val, color]) => (
            <div key={label} style={{ background: "#0a1520", borderRadius: 10, padding: "14px 10px", textAlign: "center", border: "1px solid #1e293b" }}>
              <div style={{ fontSize: 24, fontWeight: 700, color }}>{val}</div>
              <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>{label}</div>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {esiCounts.filter(e => e.count > 0).map(e => (
            <div key={e.level} style={{
              padding: "5px 12px", borderRadius: 20, fontSize: 12, fontWeight: 600,
              background: `${esiColors[e.level]}20`, color: esiColors[e.level],
              border: `1px solid ${esiColors[e.level]}40`,
            }}>
              ESI {e.level}: {e.count}
            </div>
          ))}
          {total === 0 && <span style={{ color: "#475569", fontSize: 12 }}>No active patients in queue</span>}
        </div>
      </div>

      {reports.length > 0 && (
        <div className="card" style={{ marginTop: 0 }}>
          <h3 style={{ marginBottom: 12, color: "#e2e8f0", fontSize: 14, fontWeight: 600 }}>Recent Reports</h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#1e293b", color: "#94a3b8" }}>
                {["Generated", "By", "Patients", "Avg Wait", "Sepsis", "Admissions"].map(h => (
                  <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {reports.map((r, i) => (
                <tr key={r.id} style={{ background: i % 2 === 0 ? "#1a2332" : "#151e2d", color: "#cbd5e1" }}>
                  <td style={{ padding: "7px 12px" }}>{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
                  <td style={{ padding: "7px 12px" }}>{r.generated_by}</td>
                  <td style={{ padding: "7px 12px" }}>{r.total_patients}</td>
                  <td style={{ padding: "7px 12px" }}>{r.avg_wait_minutes?.toFixed(0)} min</td>
                  <td style={{ padding: "7px 12px", color: r.sepsis_count > 0 ? "#f87171" : "#4ade80" }}>{r.sepsis_count}</td>
                  <td style={{ padding: "7px 12px" }}>{r.admissions_predicted}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {reports.length === 0 && (
        <div className="empty-queue">
          <div className="empty-icon">📋</div>
          <div>No reports generated yet</div>
          <div className="empty-sub">Click "Download PDF" to generate your first shift report</div>
        </div>
      )}
    </div>
  );
}

function LiveLog({ logs }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);

  return (
    <div className="live-log" ref={ref}>
      {logs.map((log, i) => (
        <div key={i} className={`log-line zone-${log.zone}`}>
          <span className="log-time">{log.time}</span>
          <span className="log-zone">Z{log.zone || "✓"}</span>
          <span>{log.message}</span>
        </div>
      ))}
    </div>
  );
}

const COMPLAINT_CATEGORIES = {
  "Cardiac": ["chest pain", "palpitations", "shortness of breath", "syncope"],
  "Respiratory": ["difficulty breathing", "wheezing", "coughing blood", "respiratory distress"],
  "Neurological": ["severe headache", "dizziness", "stroke symptoms", "seizure", "altered consciousness"],
  "GI / Abdominal": ["abdominal pain", "nausea & vomiting", "rectal bleeding", "severe diarrhea"],
  "Trauma / MSK": ["fall injury", "fracture", "back pain", "limb swelling", "wound / laceration"],
  "Infection / Systemic": ["fever & chills", "sepsis symptoms", "rash", "swollen lymph nodes"],
  "Psych / Other": ["anxiety / panic", "suicidal ideation", "mental health crisis", "allergic reaction", "eye pain", "urinary symptoms"],
};

const PAGE_TITLES = {
  scanner:    "Patient Scanner",
  queue:      "ER Queue",
  analytics:  "Command Dashboard",
  beds:       "Bed Board",
  report:     "Shift Report",
  journeys:   "Clinical Journeys",
  audit:      "Audit Log",
  compliance: "Compliance Center",
  billing:    "Billing",
};

const NAV_ITEMS = [
  { id: "scanner",   icon: "📡", label: "Patient Scanner" },
  { id: "queue",     icon: "🏥", label: "ER Queue",       badge: true },
  { id: "analytics", icon: "📊", label: "Command",        },
  { id: "beds",      icon: "🛏", label: "Bed Board",      },
  { id: "journeys",  icon: "🩺", label: "Journeys",       journeyBadge: true },
];

const STAFF_NAV = [
  { id: "report",    icon: "📋", label: "Shift Report" },
];

const ADMIN_NAV = [
  { id: "audit",      icon: "🔒", label: "Audit Log" },
  { id: "compliance", icon: "🛡", label: "Compliance" },
  { id: "billing",    icon: "💳", label: "Billing" },
];

export default function App() {
  const { user, logout } = useAuth();
  const [showDemo, setShowDemo] = useState(false);
  const [form, setForm] = useState({ name: "", age: "", phone: "" });
  const [selectedComplaints, setSelectedComplaints] = useState([]);
  const [customComplaint, setCustomComplaint] = useState("");
  const [scanning, setScanning] = useState(false);
  const [zoneStatus, setZoneStatus] = useState({ 1: "idle", 2: "idle", 3: "idle", 4: "idle", 5: "idle" });
  const [sensorData, setSensorData] = useState(null);
  const [biometricData, setBiometricData] = useState(null);
  const [ehrData, setEhrData] = useState(null);
  const [insuranceData, setInsuranceData] = useState(null);
  const [triageData, setTriageData] = useState(null);
  const [routingData, setRoutingData] = useState(null);
  const [zone5Data, setZone5Data] = useState(null);
  const [queue, setQueue] = useState([]);
  const [logs, setLogs] = useState([]);
  const [scanComplete, setScanComplete] = useState(false);
  const [activeTab, setActiveTab] = useState("scanner");
  const [toasts, setToasts] = useState([]);
  const [journeyEscalations, setJourneyEscalations] = useState(0);
  const [soapModal, setSoapModal] = useState(null); // { patientId, patientName, note }
  const [soapLoading, setSoapLoading] = useState(false);
  const [soapEditing, setSoapEditing] = useState(false);
  const [soapEdits, setSoapEdits] = useState({});

  const addLog = (zone, message) => {
    const time = new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    setLogs((prev) => [...prev, { zone, message, time }]);
  };

  const setZone = (num, status) => {
    setZoneStatus((prev) => ({ ...prev, [num]: status }));
  };

  const toggleComplaint = (c) => {
    setSelectedComplaints(prev =>
      prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]
    );
  };

  const addCustomComplaint = () => {
    const val = customComplaint.trim();
    if (val && !selectedComplaints.includes(val)) {
      setSelectedComplaints(prev => [...prev, val]);
    }
    setCustomComplaint("");
  };

  const removeComplaint = (c) => setSelectedComplaints(prev => prev.filter(x => x !== c));

  const resetScan = () => {
    setZoneStatus({ 1: "idle", 2: "idle", 3: "idle", 4: "idle", 5: "idle" });
    setSensorData(null);
    setBiometricData(null);
    setEhrData(null);
    setInsuranceData(null);
    setTriageData(null);
    setRoutingData(null);
    setZone5Data(null);
    setScanComplete(false);
    setLogs([]);
    setSelectedComplaints([]);
    setCustomComplaint("");
    setForm(f => ({ ...f, phone: "" }));
  };

  const authHeaders = () => ({
    Authorization: `Bearer ${user?.token}`,
  });

  const addToast = useCallback((msg) => {
    const id = Date.now();
    setToasts(prev => [...prev.slice(-4), { id, ...msg }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 8000);
  }, []);

  // WebSocket — real-time queue/bed/alert updates
  const handleWsMsg = useCallback((msg) => {
    switch (msg.event) {
      case "patient_added":
        setQueue(prev => {
          if (prev.find(p => p.patient_id === msg.patient_id)) return prev;
          return [...prev, msg].sort((a, b) => a.esi_level - b.esi_level);
        });
        break;
      case "patient_discharged":
        setQueue(prev => prev.filter(p => p.patient_id !== msg.patient_id));
        break;
      case "monitor_alert": {
        const a = msg.alert || {};
        addToast({ level: a.level || "warning", text: a.message || "Clinical alert" });
        break;
      }
      case "journey_escalation":
        setJourneyEscalations(n => n + 1);
        addToast({ level: "critical", text: `🚨 Journey escalation: ${msg.name} reported worsening symptoms` });
        break;
      default: break;
    }
  }, [addToast]);

  const wsUrl = user?.token ? `${WS_BASE}/ws?token=${user.token}` : null;
  const { connected: wsConnected } = useWebSocket(wsUrl, handleWsMsg);

  const fetchQueue = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/queue`, { headers: { Authorization: `Bearer ${user?.token}` } });
      const data = await res.json();
      setQueue(data);
    } catch (e) {
      console.error("Queue fetch error:", e);
    }
  }, [user?.token]);

  const dischargePatient = async (patientId) => {
    await fetch(`${API_BASE}/queue/${patientId}`, { method: "DELETE", headers: authHeaders() });
    setTimeout(fetchQueue, 500);
  };

  const generateSoap = useCallback(async (patient) => {
    setSoapModal({ patientId: patient.patient_id, patientName: patient.name, note: null });
    setSoapLoading(true);
    try {
      const res = await fetch(`${API_BASE}/chart/note/${patient.patient_id}/generate`, {
        method: "POST", headers: { Authorization: `Bearer ${user?.token}` },
      });
      const note = await res.json();
      setSoapModal({ patientId: patient.patient_id, patientName: patient.name, note });
    } catch {
      setSoapModal(null);
    } finally {
      setSoapLoading(false);
    }
  }, [user?.token]);

  useEffect(() => {
    fetchQueue(); // initial load; WS handles live updates thereafter
  }, [fetchQueue]);

  const startScan = () => {
    const allComplaints = selectedComplaints.join(", ");
    if (!form.name || !form.age || !allComplaints) {
      alert("Please enter name, age, and at least one complaint.");
      return;
    }

    const savedComplaints = [...selectedComplaints];
    resetScan();
    setSelectedComplaints(savedComplaints);
    setScanning(true);
    setActiveTab("scanner");

    const params = new URLSearchParams({
      name: form.name,
      age: form.age,
      chief_complaint: allComplaints,
      token: user?.token,
    });
    if (form.phone) params.append("phone", form.phone);

    const evtSource = new EventSource(`${API_BASE}/scan/stream?${params}`);

    evtSource.onmessage = (e) => {
      const payload = JSON.parse(e.data);
      const { event, zone, message, data } = payload;

      addLog(zone, message);

      switch (event) {
        case "zone1_start":
          setZone(1, "active");
          break;
        case "zone1_complete":
          setZone(1, "done");
          setSensorData(data);
          break;
        case "zone2_start":
          setZone(2, "active");
          break;
        case "zone2_biometric":
          setBiometricData(data);
          break;
        case "zone2_ehr":
          setEhrData(data);
          break;
        case "zone2_insurance":
          setInsuranceData(data);
          setZone(2, "done");
          break;
        case "zone3_start":
        case "zone3_llm":
          setZone(3, "active");
          break;
        case "zone3_complete":
          setZone(3, "done");
          setTriageData(data);
          break;
        case "zone4_routing":
          setZone(4, "done");
          setRoutingData(data);
          break;
        case "zone5_complete":
          setZone(5, "done");
          setZone5Data(data);
          break;
        case "scan_complete":
          setScanComplete(true);
          setScanning(false);
          fetchQueue();
          evtSource.close();
          break;
        default:
          break;
      }
    };

    evtSource.onerror = () => {
      addLog(0, "Connection error — check backend");
      setScanning(false);
      evtSource.close();
    };
  };

  const criticalCount = queue.filter(p => p.esi_level === 1).length;
  const allNav = [
    ...NAV_ITEMS,
    ...STAFF_NAV,
    ...(user?.role === "admin" ? ADMIN_NAV : []),
  ];

  return (
    <div className="app-shell">
      {showDemo && <DemoPlayer onClose={() => setShowDemo(false)} />}

      {/* Toast notifications */}
      {toasts.length > 0 && (
        <div className="toast-stack">
          {toasts.map(t => (
            <div
              key={t.id}
              className={`toast ${t.level}`}
              onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))}
            >
              {t.level === "critical" ? "🚨 " : t.level === "warning" ? "⚠️ " : "ℹ️ "}{t.text}
            </div>
          ))}
        </div>
      )}

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon">⚕</div>
          <div>
            <div className="sidebar-brand-name">MediScan</div>
            <div className="sidebar-brand-sub">Gateway v2</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {allNav.map(item => (
            <button
              key={item.id}
              className={`nav-item ${activeTab === item.id ? "active" : ""}`}
              onClick={() => setActiveTab(item.id)}
            >
              <span className="nav-item-icon">{item.icon}</span>
              {item.label}
              {item.badge && queue.length > 0 && (
                <span className="nav-badge">{queue.length}</span>
              )}
              {item.id === "queue" && criticalCount > 0 && (
                <span className="nav-badge" style={{ background: "var(--esi-1)" }}>{criticalCount}!</span>
              )}
              {item.journeyBadge && journeyEscalations > 0 && (
                <span className="journey-alert-dot" title={`${journeyEscalations} escalation(s)`} />
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="ws-indicator">
            <div className={`ws-dot ${wsConnected ? "online" : "offline"}`} />
            {wsConnected ? "Live updates" : "Reconnecting…"}
          </div>
          <button className="demo-btn" style={{ width: "100%", fontSize: 12, padding: "8px" }} onClick={() => setShowDemo(true)}>
            ▶ Run Demo
          </button>
          <a
            href="/check"
            target="_blank"
            rel="noopener noreferrer"
            className="demo-btn"
            style={{ display: "block", width: "100%", fontSize: 12, padding: "8px", textAlign: "center", textDecoration: "none", marginTop: 6, color: "#5eead4", borderColor: "#0d9488" }}
          >
            🩺 CareNavigator
          </a>
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">{user?.name?.[0] || "?"}</div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">{user?.name}</div>
              <div className="sidebar-user-role">{user?.role}</div>
            </div>
            <button className="signout-btn" onClick={logout} title="Sign out">⎋</button>
          </div>
        </div>
      </aside>

      {/* Main area */}
      <div className="main-area">
        <header className="topbar">
          <div className="topbar-title">{PAGE_TITLES[activeTab]}</div>
          <div className="topbar-stats">
            {criticalCount > 0 && <span className="stat-pill critical">🚨 {criticalCount} Critical</span>}
            <span className="stat-pill high">{queue.filter(p => p.esi_level <= 2).length} High Acuity</span>
            <span className="stat-pill">{queue.length} In Queue</span>
            <span className={`stat-pill ${wsConnected ? "online" : ""}`}>
              {wsConnected ? "⬤ Live" : "⬤ Offline"}
            </span>
          </div>
        </header>

      <main className="content-area">
        {activeTab === "scanner" && (
          <div className="scanner-layout">
            {/* LEFT — Input + Portal */}
            <div className="left-panel">
              <div className="card">
                <h2 className="card-title">Patient Entry</h2>
                <div className="form-group">
                  <label>Full Name</label>
                  <input
                    placeholder="e.g. James Okonkwo"
                    value={form.name}
                    onChange={e => setForm({ ...form, name: e.target.value })}
                    disabled={scanning}
                  />
                </div>
                <div className="form-group">
                  <label>Age</label>
                  <input
                    type="number"
                    placeholder="e.g. 58"
                    value={form.age}
                    onChange={e => setForm({ ...form, age: e.target.value })}
                    disabled={scanning}
                  />
                </div>
                <div className="form-group">
                  <label>Mobile Phone <span style={{color:"#94a3b8",fontWeight:400}}>(optional — SMS updates)</span></label>
                  <input
                    type="tel"
                    placeholder="e.g. +13125551234"
                    value={form.phone}
                    onChange={e => setForm({ ...form, phone: e.target.value })}
                    disabled={scanning}
                  />
                </div>
                {/* Selected complaints display */}
                {selectedComplaints.length > 0 && (
                  <div className="selected-complaints">
                    <label>Selected ({selectedComplaints.length})</label>
                    <div className="selected-chips">
                      {selectedComplaints.map(c => (
                        <span key={c} className="selected-chip">
                          {c}
                          {!scanning && (
                            <button className="chip-remove" onClick={() => removeComplaint(c)}>×</button>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Category complaint picker */}
                {!scanning && (
                  <div className="complaint-picker">
                    <label>Chief Complaints & Diagnoses</label>
                    {Object.entries(COMPLAINT_CATEGORIES).map(([category, items]) => (
                      <div key={category} className="complaint-category">
                        <div className="complaint-category-label">{category}</div>
                        <div className="complaint-chips">
                          {items.map(c => (
                            <button
                              key={c}
                              className={`complaint-chip ${selectedComplaints.includes(c) ? "active" : ""}`}
                              onClick={() => toggleComplaint(c)}
                            >
                              {selectedComplaints.includes(c) && <span className="chip-check">✓ </span>}
                              {c}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}

                    {/* Custom complaint input */}
                    <div className="custom-complaint">
                      <input
                        placeholder="Add custom complaint or diagnosis..."
                        value={customComplaint}
                        onChange={e => setCustomComplaint(e.target.value)}
                        onKeyDown={e => e.key === "Enter" && addCustomComplaint()}
                      />
                      <button className="add-custom-btn" onClick={addCustomComplaint}>+ Add</button>
                    </div>
                  </div>
                )}


                <button
                  className={`scan-btn ${scanning ? "scanning" : ""}`}
                  onClick={startScan}
                  disabled={scanning}
                >
                  {scanning ? (
                    <><span className="btn-spinner" /> Scanning Patient...</>
                  ) : (
                    <>🚶 Start Walk-Through Scan</>
                  )}
                </button>

                {scanComplete && (
                  <button className="reset-btn" onClick={resetScan}>
                    ↺ New Patient
                  </button>
                )}
              </div>

              <SensorPortal active={zoneStatus[1] === "active"} />

              {logs.length > 0 && (
                <div className="card">
                  <h3 className="card-title">Live System Log</h3>
                  <LiveLog logs={logs} />
                </div>
              )}
            </div>

            {/* RIGHT — Zone pipeline */}
            <div className="right-panel">
              <ZoneStep zoneNum={1} label={ZONE_LABELS[1]} status={zoneStatus[1]}>
                <SensorCard data={sensorData} />
              </ZoneStep>

              <ZoneStep zoneNum={2} label={ZONE_LABELS[2]} status={zoneStatus[2]}>
                {biometricData && (
                  <div className="info-row">
                    <span>👤 {biometricData.name}</span>
                    <span>ID: {biometricData.patient_id}</span>
                    <span>Match: {(biometricData.face_match_confidence * 100).toFixed(1)}%</span>
                  </div>
                )}
                {ehrData && ehrData.history?.length > 0 && (
                  <div className="ehr-row">
                    <b>History:</b> {ehrData.history.join(", ")}
                    {ehrData.allergies?.length > 0 && <> · <b>Allergies:</b> {ehrData.allergies.join(", ")}</>}
                  </div>
                )}
                {insuranceData && (
                  <div className="insurance-row">
                    🏦 {insuranceData.provider} — {insuranceData.plan_type} — Co-pay: <b>${insuranceData.copay.toFixed(0)}</b>
                    {insuranceData.eligible ? " ✓ Eligible" : " ✗ Not eligible"}
                  </div>
                )}
              </ZoneStep>

              <ZoneStep zoneNum={3} label={ZONE_LABELS[3]} status={zoneStatus[3]}>
                <TriageCard data={triageData} />
              </ZoneStep>

              <ZoneStep zoneNum={4} label={ZONE_LABELS[4]} status={zoneStatus[4]}>
                {routingData && (
                  <div className={`routing-card esi-${routingData.esi_level}`}>
                    <div className="routing-esi" style={{ background: ESI_CONFIG[routingData.esi_level]?.color }}>
                      ESI {routingData.esi_level}
                    </div>
                    <div className="routing-info">
                      <strong>{routingData.destination}</strong>
                      <span> → {routingData.room}</span>
                    </div>
                  </div>
                )}
              </ZoneStep>

              <ZoneStep zoneNum={5} label={ZONE_LABELS[5]} status={zoneStatus[5]}>
                {zone5Data && (
                  <div className="zone5-grid">
                    <div className="z5-item">
                      <div className="z5-icon">💳</div>
                      <div className="z5-label">Wristband</div>
                      <div className="z5-val">{zone5Data.wristband?.nfc_id}</div>
                    </div>
                    <div className="z5-item">
                      <div className="z5-icon">📱</div>
                      <div className="z5-label">Phone Push</div>
                      <div className="z5-val">{zone5Data.phone_push?.sent ? "Sent ✓" : "Not sent"}</div>
                    </div>
                    <div className="z5-item">
                      <div className="z5-icon">👨‍👩‍👧</div>
                      <div className="z5-label">Family Alert</div>
                      <div className="z5-val">{zone5Data.family_alert?.sent ? "Sent ✓" : "Not triggered"}</div>
                    </div>
                    <div className="z5-item">
                      <div className="z5-icon">📋</div>
                      <div className="z5-label">Orders Pre-staged</div>
                      <div className="z5-val">{zone5Data.care_orders?.order_count} orders in Epic</div>
                    </div>
                  </div>
                )}
              </ZoneStep>

              {scanComplete && triageData && (
                <div className="complete-banner" style={{ borderColor: ESI_CONFIG[triageData.esi_level]?.color, background: ESI_CONFIG[triageData.esi_level]?.bg }}>
                  <div className="complete-icon">{ESI_CONFIG[triageData.esi_level]?.icon}</div>
                  <div>
                    <div className="complete-title">Patient Checked In — {triageData.priority_label}</div>
                    <div className="complete-sub">Total processing time: &lt;15 seconds</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "queue" && (
          <div className="queue-layout">
            <div className="queue-header">
              <h2>Live ER Queue</h2>
              <div className="queue-controls">
                <button className="refresh-btn" onClick={fetchQueue}>↻ Refresh</button>
                {queue.length > 0 && (
                  <button className="clear-btn" onClick={async () => {
                    await fetch(`${API_BASE}/queue`, { method: "DELETE", headers: authHeaders() });
                    setQueue([]);
                  }}>Clear All</button>
                )}
              </div>
            </div>

            {[1, 2, 3, 4, 5].map(esi => {
              const patients = queue.filter(p => p.esi_level === esi);
              if (patients.length === 0) return null;
              const cfg = ESI_CONFIG[esi];
              return (
                <div key={esi} className="queue-section">
                  <div className="queue-section-header" style={{ background: cfg.color }}>
                    {cfg.icon} ESI {esi} — {cfg.label} ({patients.length})
                  </div>
                  <div className="queue-cards">
                    {patients.map(p => (
                      <PatientQueueCard key={p.patient_id} patient={p} onDischarge={dischargePatient} onSOAP={generateSoap} />
                    ))}
                  </div>
                </div>
              );
            })}

            {queue.length === 0 && (
              <div className="empty-queue">
                <div className="empty-icon">🏥</div>
                <div>No patients in queue</div>
                <div className="empty-sub">Run a walk-through scan to add patients</div>
              </div>
            )}
          </div>
        )}

        {activeTab === "analytics" && <OutcomesDashboard user={user} />}
        {activeTab === "beds" && <BedBoard user={user} />}
        {activeTab === "report"     && <ShiftReportPanel user={user} queue={queue} />}
        {activeTab === "billing"    && <BillingPage user={user} />}
        {activeTab === "audit"      && <AuditLogPanel user={user} />}
        {activeTab === "journeys"   && <ClinicalJourneys activeTab="journeys" />}
        {activeTab === "compliance" && <ClinicalJourneys activeTab="compliance" />}
      </main>
      </div>

      {/* SOAP Note Modal */}
      {(soapModal || soapLoading) && (
        <div className="soap-overlay" onClick={() => { setSoapModal(null); setSoapEditing(false); setSoapEdits({}); }}>
          <div className="soap-modal" onClick={e => e.stopPropagation()}>
            <div className="soap-modal-header">
              <h2>📝 SOAP Note — {soapModal?.patientName}</h2>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                {soapModal?.note && !soapModal?.note?.finalized && (
                  <button
                    className="soap-copy-btn"
                    style={{ padding: "4px 12px", fontSize: 12 }}
                    onClick={() => {
                      if (soapEditing) { setSoapEditing(false); setSoapEdits({}); }
                      else { setSoapEditing(true); setSoapEdits({ ...soapModal.note }); }
                    }}
                  >
                    {soapEditing ? "Cancel Edit" : "✏ Edit"}
                  </button>
                )}
                <button className="soap-close" onClick={() => { setSoapModal(null); setSoapEditing(false); setSoapEdits({}); }}>✕</button>
              </div>
            </div>
            {soapLoading ? (
              <div className="soap-loading">
                <div className="soap-spinner" />
                <p>Generating clinical note…</p>
              </div>
            ) : soapModal?.note ? (
              <div className="soap-body">
                {["subjective", "objective", "assessment", "plan"].map(section => (
                  <div key={section} className="soap-section">
                    <div className="soap-section-title">{section.toUpperCase()}</div>
                    {soapEditing ? (
                      <textarea
                        className="soap-edit-textarea"
                        value={soapEdits[section] ?? soapModal.note[section] ?? ""}
                        onChange={e => setSoapEdits(prev => ({ ...prev, [section]: e.target.value }))}
                        rows={4}
                      />
                    ) : (
                      <div className="soap-section-text">{soapModal.note[section]}</div>
                    )}
                  </div>
                ))}
                <div className="soap-meta">
                  {soapModal.note.finalized
                    ? `✓ Finalized by ${soapModal.note.finalized_by}`
                    : `Generated by AI · ${new Date(soapModal.note.generated_at).toLocaleString()} · Review before finalizing`}
                </div>
                <div className="soap-actions">
                  {soapEditing ? (
                    <button className="soap-finalize-btn" onClick={async () => {
                      await fetch(`${API_BASE}/chart/note/${soapModal.patientId}`, {
                        method: "PATCH",
                        headers: { ...authHeaders(), "Content-Type": "application/json" },
                        body: JSON.stringify(soapEdits),
                      });
                      setSoapModal(prev => ({ ...prev, note: { ...prev.note, ...soapEdits } }));
                      setSoapEditing(false);
                      setSoapEdits({});
                      addToast({ level: "info", text: "SOAP note saved" });
                    }}>
                      💾 Save Changes
                    </button>
                  ) : (
                    <button className="soap-copy-btn" onClick={() => {
                      navigator.clipboard.writeText(soapModal.note.full_text);
                      addToast({ level: "info", text: "SOAP note copied to clipboard" });
                    }}>
                      📋 Copy Full Note
                    </button>
                  )}
                  {user?.role === "physician" && !soapModal?.note?.finalized && !soapEditing && (
                    <button className="soap-finalize-btn" onClick={async () => {
                      await fetch(`${API_BASE}/chart/note/${soapModal.patientId}/finalize`, {
                        method: "POST", headers: authHeaders(),
                      });
                      setSoapModal(prev => ({ ...prev, note: { ...prev.note, finalized: true, finalized_by: user.username } }));
                      addToast({ level: "info", text: "SOAP note finalized and signed" });
                    }}>
                      ✓ Finalize & Sign
                    </button>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
