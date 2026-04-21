import React, { useState, useRef, useEffect, useCallback } from "react";
import "./App.css";
import { useAuth, API_BASE } from "./AuthContext";

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

function PatientQueueCard({ patient, onDischarge }) {
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

      <button className="discharge-btn" onClick={() => onDischarge(patient.patient_id)}>
        Discharge
      </button>
    </div>
  );
}

function AnalyticsDashboard({ user }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/analytics`, {
        headers: { Authorization: `Bearer ${user?.token}` },
      });
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error("Analytics error:", e);
    } finally {
      setLoading(false);
    }
  }, [user?.token]);

  useEffect(() => {
    fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 15000);
    return () => clearInterval(interval);
  }, [fetchAnalytics]);

  if (loading) return <div className="analytics-loading">Loading analytics...</div>;
  if (!data) return null;

  const cap = data.capacity;
  const q = data.queue;
  const perf = data.performance;

  const capColor = cap.status === "critical" ? "#dc2626" : cap.status === "high" ? "#ea580c" : cap.status === "moderate" ? "#ca8a04" : "#22c55e";

  return (
    <div className="analytics-layout">
      {/* Live Alerts */}
      {data.alerts?.length > 0 && (
        <div className="alert-strip">
          {data.alerts.map((a, i) => (
            <div key={i} className={`alert-item alert-${a.level}`}>
              {a.level === "critical" ? "🚨" : a.level === "warning" ? "⚠️" : "ℹ️"} {a.message}
            </div>
          ))}
        </div>
      )}

      {/* Capacity Overview */}
      <div className="analytics-section">
        <h3 className="section-title">ED Capacity</h3>
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-val" style={{ color: capColor }}>{cap.occupancy_percent}%</div>
            <div className="metric-label">Occupancy</div>
            <div className="capacity-bar"><div className="capacity-fill" style={{ width: `${cap.occupancy_percent}%`, background: capColor }} /></div>
          </div>
          <div className="metric-card">
            <div className="metric-val">{cap.occupied_beds}<span className="metric-sub">/{cap.total_beds}</span></div>
            <div className="metric-label">Beds Occupied</div>
          </div>
          <div className="metric-card">
            <div className="metric-val" style={{ color: cap.boarding_patients > 3 ? "#ea580c" : "#94a3b8" }}>{cap.boarding_patients}</div>
            <div className="metric-label">Boarding Patients</div>
          </div>
          <div className="metric-card">
            <div className="metric-val" style={{ color: "#22c55e" }}>{perf.door_to_triage_seconds}s</div>
            <div className="metric-label">Door-to-Triage</div>
            <div className="metric-note">National avg: 28 min</div>
          </div>
        </div>
      </div>

      {/* Queue Intelligence */}
      <div className="analytics-section">
        <h3 className="section-title">Queue Intelligence</h3>
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-val">{q.total_patients}</div>
            <div className="metric-label">In Queue</div>
          </div>
          <div className="metric-card">
            <div className="metric-val">{q.avg_wait_minutes} min</div>
            <div className="metric-label">Avg Wait</div>
            <div className="metric-note">National avg: 162 min</div>
          </div>
          <div className="metric-card">
            <div className="metric-val" style={{ color: q.sepsis_alerts > 0 ? "#dc2626" : "#22c55e" }}>{q.sepsis_alerts}</div>
            <div className="metric-label">Sepsis Alerts</div>
          </div>
          <div className="metric-card">
            <div className="metric-val" style={{ color: q.behavioral_health > 0 ? "#a78bfa" : "#94a3b8" }}>{q.behavioral_health}</div>
            <div className="metric-label">Behavioral Health</div>
          </div>
          <div className="metric-card">
            <div className="metric-val" style={{ color: q.admission_likely > 0 ? "#f97316" : "#94a3b8" }}>{q.admission_likely}</div>
            <div className="metric-label">Likely Admissions</div>
          </div>
          <div className="metric-card">
            <div className="metric-val" style={{ color: q.lwbs_high_risk > 0 ? "#ca8a04" : "#22c55e" }}>{q.lwbs_high_risk}</div>
            <div className="metric-label">LWBS Risk</div>
          </div>
        </div>
      </div>

      {/* ESI Breakdown */}
      <div className="analytics-section">
        <h3 className="section-title">ESI Breakdown</h3>
        <div className="esi-breakdown">
          {[1,2,3,4,5].map(esi => {
            const cfg = ESI_CONFIG[esi];
            const count = q.esi_breakdown?.[String(esi)] || 0;
            return (
              <div key={esi} className="esi-bar-item">
                <div className="esi-bar-label" style={{ color: cfg.color }}>ESI {esi}</div>
                <div className="esi-bar-track">
                  <div className="esi-bar-fill" style={{ width: count > 0 ? `${Math.min(100, count * 20)}%` : "0%", background: cfg.color }} />
                </div>
                <div className="esi-bar-count" style={{ color: cfg.color }}>{count}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Performance vs National */}
      <div className="analytics-section">
        <h3 className="section-title">MediScan vs National Average</h3>
        <div className="comparison-table">
          <div className="comp-row">
            <span className="comp-metric">Door-to-Triage</span>
            <span className="comp-national">28 min national avg</span>
            <span className="comp-mediscan" style={{ color: "#22c55e" }}>{perf.door_to_triage_seconds}s ↓97%</span>
          </div>
          <div className="comp-row">
            <span className="comp-metric">LWBS Rate</span>
            <span className="comp-national">5%+ national avg</span>
            <span className="comp-mediscan" style={{ color: "#22c55e" }}>{perf.lwbs_rate_today}% today</span>
          </div>
          <div className="comp-row">
            <span className="comp-metric">Avg LOS</span>
            <span className="comp-national">162 min national avg</span>
            <span className="comp-mediscan" style={{ color: perf.avg_los_minutes < 162 ? "#22c55e" : "#f97316" }}>{perf.avg_los_minutes} min</span>
          </div>
          <div className="comp-row">
            <span className="comp-metric">Patients Seen Today</span>
            <span className="comp-national">—</span>
            <span className="comp-mediscan">{perf.patients_seen_today}</span>
          </div>
        </div>
      </div>
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

export default function App() {
  const { user, logout } = useAuth();
  const [form, setForm] = useState({ name: "", age: "" });
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
  };

  const authHeaders = () => ({
    Authorization: `Bearer ${user?.token}`,
  });

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
    fetchQueue();
  };

  useEffect(() => {
    fetchQueue();
    const interval = setInterval(fetchQueue, 10000);
    return () => clearInterval(interval);
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

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="header-inner">
          <div className="header-logo">
            <span className="logo-icon">⚕</span>
            <div>
              <div className="logo-title">MediScan Gateway</div>
              <div className="logo-sub">AI-Powered Walk-Through Patient Intake & Instant Triage</div>
            </div>
          </div>
          <div className="header-stats">
            <div className="stat-pill critical">{queue.filter(p => p.esi_level === 1).length} Critical</div>
            <div className="stat-pill urgent">{queue.filter(p => p.esi_level <= 2).length} High Acuity</div>
            <div className="stat-pill total">{queue.length} In Queue</div>
            <div className="header-user">
              <span className="user-name">{user?.name}</span>
              <span className="user-role">{user?.role}</span>
              <button className="logout-btn" onClick={logout}>Sign Out</button>
            </div>
          </div>
        </div>
      </header>

      <div className="app-tabs">
        <button className={`tab ${activeTab === "scanner" ? "active" : ""}`} onClick={() => setActiveTab("scanner")}>
          📡 Patient Scanner
        </button>
        <button className={`tab ${activeTab === "queue" ? "active" : ""}`} onClick={() => setActiveTab("queue")}>
          🏥 ER Queue {queue.length > 0 && <span className="tab-badge">{queue.length}</span>}
        </button>
        <button className={`tab ${activeTab === "analytics" ? "active" : ""}`} onClick={() => setActiveTab("analytics")}>
          📊 Command Dashboard
        </button>
      </div>

      <main className="app-main">
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
                      <PatientQueueCard key={p.patient_id} patient={p} onDischarge={dischargePatient} />
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

        {activeTab === "analytics" && <AnalyticsDashboard user={user} />}
      </main>
    </div>
  );
}
