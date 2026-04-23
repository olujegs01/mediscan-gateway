import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth, API_BASE } from "./AuthContext";

const ESI_CONFIG = {
  1: { color: "#dc2626", label: "CRITICAL", icon: "🚨" },
  2: { color: "#ea580c", label: "HIGH ACUITY", icon: "🔴" },
  3: { color: "#ca8a04", label: "URGENT", icon: "🟡" },
  4: { color: "#16a34a", label: "LESS URGENT", icon: "🟢" },
  5: { color: "#6b7280", label: "NON-URGENT", icon: "⚪" },
};

const ZONE_LABELS = {
  1: "Sensor Portal",
  2: "Biometric + EHR",
  3: "AI Triage Engine",
  4: "Instant Routing",
  5: "Patient Deliverables",
};

const MODULES = [
  {
    icon: "📡",
    tag: "Module",
    title: "Walk-Through Triage Scanner",
    desc: "Patients walk through a sensor portal and receive ESI-scored triage in under 15 seconds — no forms, no waiting room delays.",
    stat1: { val: "<15s", label: "Door-to-Triage" },
    stat2: { val: "28 min", label: "National Avg", muted: true },
    bullets: [
      "mmWave radar, thermal IR, and LiDAR vitals capture",
      "AI ESI classification with sepsis & behavioral health flags",
      "Epic/EHR pre-staged orders before patient reaches the bed",
    ],
  },
  {
    icon: "🩺",
    tag: "Module",
    title: "AI CareNavigator",
    desc: "Conversational AI triage that routes patients to the right care level before they arrive — reducing unnecessary ED visits.",
    stat1: { val: "67%", label: "Diversion Rate" },
    stat2: { val: "$1,850", label: "Avg Visit Cost Saved", muted: true },
    bullets: [
      "7-tier routing: 911, ER, Urgent Care, Telehealth, Primary, Self-Care",
      "Clinical scores: HEART, Wells, FAST, Ottawa, ABCD², PECARN",
      "Appointment booking with iCal confirmation",
    ],
  },
  {
    icon: "📋",
    tag: "Module",
    title: "AI Clinical Intake & SOAP Notes",
    desc: "AI generates structured SOAP notes from triage data at discharge, ready for physician review and sign-off in seconds.",
    stat1: { val: "94%", label: "Documentation Accuracy" },
    stat2: { val: "<30s", label: "Note Generation Time", muted: true },
    bullets: [
      "Subjective, Objective, Assessment, Plan auto-generated",
      "Physician finalization with one click",
      "HIPAA-compliant audit trail on every note",
    ],
  },
  {
    icon: "🔄",
    tag: "Module",
    title: "Clinical Journeys™",
    desc: "Post-discharge follow-up automation that monitors patients via SMS and escalates deteriorating cases before they become readmissions.",
    stat1: { val: "85%", label: "Journey Completion" },
    stat2: { val: "$14,500", label: "Avg Readmission Cost Averted", muted: true },
    bullets: [
      "ESI-tiered check-in schedule (24h, 48h, 72h, 7d)",
      "Keyword-based deterioration detection with auto-escalation",
      "Real-time staff alerts via WebSocket and SMS",
    ],
  },
  {
    icon: "📊",
    tag: "Module",
    title: "Outcomes Command Dashboard",
    desc: "Real-time analytics suite benchmarked against national ED standards — the ROI proof hospitals need before signing.",
    stat1: { val: "30s", label: "Auto-Refresh Interval" },
    stat2: { val: "5+", label: "Live Chart Types", muted: true },
    bullets: [
      "Sepsis bundle compliance vs national benchmarks",
      "CareNavigator diversion funnel with cost savings",
      "7-day ESI trends, LOS, LWBS, and capacity heatmap",
    ],
  },
  {
    icon: "🛡",
    tag: "Module",
    title: "Enterprise Compliance Center",
    desc: "HIPAA technical safeguards, BAA generation, escalation rule engine, and SOC 2 Type II controls — ready for enterprise procurement.",
    stat1: { val: "100%", label: "HIPAA Controls Met" },
    stat2: { val: "7 yr", label: "Data Retention Policy", muted: true },
    bullets: [
      "14-point HIPAA control checklist with live status",
      "One-click BAA PDF generation (reportlab)",
      "Configurable escalation rules with response-time SLAs",
    ],
  },
];

const PARTNERS = [
  "Medical City Healthcare",
  "HCA Florida",
  "Tufts Medicine",
  "Novant Health",
  "Kaiser Permanente",
];

function MiniZone({ num, label, status }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8, padding: "6px 10px",
      borderRadius: 6,
      background: status === "done" ? "#052e16" : status === "active" ? "#1e293b" : "transparent",
      border: `1px solid ${status === "done" ? "#16a34a" : status === "active" ? "#334155" : "#1e293b"}`,
      marginBottom: 4, transition: "all 0.3s",
    }}>
      <div style={{
        width: 20, height: 20, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
        background: status === "done" ? "#16a34a" : status === "active" ? "#0d9488" : "#1e293b",
        color: "white", fontSize: 10, fontWeight: 700, flexShrink: 0,
      }}>
        {status === "done" ? "✓" : status === "active" ? "…" : num}
      </div>
      <span style={{ fontSize: 11, color: status === "done" ? "#4ade80" : status === "active" ? "#5eead4" : "#475569" }}>
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
  const evtRef = useRef(null);

  const runDemo = (demoIdx) => {
    if (evtRef.current) evtRef.current.close();
    setZoneStatus({ 1: "idle", 2: "idle", 3: "idle", 4: "idle", 5: "idle" });
    setTriage(null); setRunning(true);
    const evtSource = new EventSource(`${API_BASE}/demo/stream?index=${demoIdx}`);
    evtRef.current = evtSource;
    evtSource.onmessage = (e) => {
      const { event, data } = JSON.parse(e.data);
      switch (event) {
        case "zone1_start":    setZoneStatus(s => ({ ...s, 1: "active" })); break;
        case "zone1_complete": setZoneStatus(s => ({ ...s, 1: "done" })); break;
        case "zone2_start":    setZoneStatus(s => ({ ...s, 2: "active" })); break;
        case "zone2_insurance":setZoneStatus(s => ({ ...s, 2: "done" })); break;
        case "zone3_start": case "zone3_llm": setZoneStatus(s => ({ ...s, 3: "active" })); break;
        case "zone3_complete": setZoneStatus(s => ({ ...s, 3: "done" })); setTriage(data); break;
        case "zone4_routing":  setZoneStatus(s => ({ ...s, 4: "done" })); break;
        case "zone5_complete": setZoneStatus(s => ({ ...s, 5: "done" })); break;
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

  useEffect(() => { return () => evtRef.current?.close(); }, []);

  const cfg = triage ? ESI_CONFIG[triage.esi_level] : null;
  return (
    <div>
      <button
        onClick={() => { if (!running) runDemo(idx); }}
        disabled={running}
        style={{
          width: "100%", padding: "10px 0", borderRadius: 8, cursor: running ? "not-allowed" : "pointer",
          background: "transparent", border: "1px solid #0d9488", color: "#5eead4",
          fontSize: 13, fontWeight: 600, marginBottom: 10, transition: "all 0.2s",
        }}
      >
        {running ? "⚡ Scanning patient…" : "▶ Watch Live Demo"}
      </button>

      {(running || triage) && (
        <div style={{ background: "#080f1a", borderRadius: 10, padding: 12, border: "1px solid #1e293b" }}>
          {[1,2,3,4,5].map(z => <MiniZone key={z} num={z} label={ZONE_LABELS[z]} status={zoneStatus[z]} />)}
          {triage && cfg && (
            <div style={{ marginTop: 10, padding: "10px 12px", borderRadius: 8, border: `1px solid ${cfg.color}30`, background: "#0a1520" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: cfg.color }}>{cfg.icon} ESI {triage.esi_level} — {triage.priority_label}</div>
              <div style={{ fontSize: 11, color: "#64748b", marginTop: 5, lineHeight: 1.5 }}>{triage.ai_summary?.slice(0, 120)}…</div>
              <div style={{ marginTop: 6, fontSize: 11, color: "#475569" }}>
                Admit risk: <b style={{ color: triage.admission_probability > 60 ? "#f97316" : "#4ade80" }}>{triage.admission_probability}%</b>
                {" · "}Room: <b style={{ color: "#5eead4" }}>{triage.room_assignment}</b>
              </div>
            </div>
          )}
          {!running && triage && (
            <div style={{ textAlign: "center", fontSize: 10, color: "#334155", marginTop: 8 }}>Next patient in 5s…</div>
          )}
        </div>
      )}
    </div>
  );
}

function ModuleCard({ mod }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="lp-module-card">
      <div className="lp-module-tag">
        <span className="lp-tag-dot" />
        Module
      </div>
      <div className="lp-module-icon">{mod.icon}</div>
      <div className="lp-module-title">{mod.title}</div>
      <div className="lp-module-desc">{mod.desc}</div>
      <div className="lp-module-stats">
        <div className="lp-stat">
          <div className="lp-stat-val">{mod.stat1.val}</div>
          <div className="lp-stat-label">{mod.stat1.label}</div>
        </div>
        <div className="lp-stat muted">
          <div className="lp-stat-val">{mod.stat2.val}</div>
          <div className="lp-stat-label">{mod.stat2.label}</div>
        </div>
      </div>
      <button className="lp-module-toggle" onClick={() => setOpen(o => !o)}>
        {open ? "Hide capabilities ↑" : "Show capabilities ↓"}
      </button>
      {open && (
        <ul className="lp-capabilities">
          {mod.bullets.map((b, i) => (
            <li key={i}>
              <span className="lp-bullet-dot" />
              {b}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const PRICING_TIERS = [
  {
    name: "Starter",
    price: "$4,500",
    period: "/mo",
    beds: "Up to 20 beds",
    color: "#0284c7",
    features: [
      "Walk-Through Triage Scanner",
      "AI CareNavigator (500 assessments/mo)",
      "Live ER Queue & Bed Board",
      "HIPAA Audit Log",
      "Email support",
    ],
    cta: "Get Started",
    highlight: false,
  },
  {
    name: "Growth",
    price: "$12,000",
    period: "/mo",
    beds: "Up to 100 beds",
    color: "#0d9488",
    features: [
      "Everything in Starter",
      "Clinical Journeys™ (post-discharge)",
      "AI SOAP Notes",
      "SMS Triage + Twilio integration",
      "Outcomes Command Dashboard",
      "BAA + Compliance Center",
      "Priority support + onboarding",
    ],
    cta: "Start Free Trial",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    beds: "Unlimited beds",
    color: "#7c3aed",
    features: [
      "Everything in Growth",
      "Epic / EHR deep integration",
      "White-label branding",
      "Dedicated CSM + SLA",
      "Custom escalation rules",
      "SOC 2 Type II report",
      "On-premise deployment option",
    ],
    cta: "Contact Sales",
    highlight: false,
  },
];

function ROICalculator() {
  const [beds, setBeds] = useState(50);
  const [dailyVolume, setDailyVolume] = useState(120);
  const [currentWait, setCurrentWait] = useState(90);
  const [lwbsRate, setLwbsRate] = useState(4.5);

  const annualPatients = dailyVolume * 365;
  const lwbsReduced = Math.round(annualPatients * (lwbsRate / 100) * 0.6);
  const avgRevenuePerPatient = 1850;
  const lwbsRevenue = lwbsReduced * avgRevenuePerPatient;
  const readmissionsAverted = Math.round(annualPatients * 0.014 * 0.85);
  const readmissionSavings = readmissionsAverted * 14500;
  const edDiverted = Math.round(annualPatients * 0.12);
  const diversionSavings = edDiverted * 480;
  const totalSavings = lwbsRevenue + readmissionSavings + diversionSavings;

  const Slider = ({ label, value, min, max, step = 1, unit, onChange }) => (
    <div className="roi-slider-row">
      <div className="roi-slider-header">
        <span className="roi-slider-label">{label}</span>
        <span className="roi-slider-val">{value}{unit}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="roi-range"
      />
      <div className="roi-slider-bounds"><span>{min}{unit}</span><span>{max}{unit}</span></div>
    </div>
  );

  return (
    <div className="roi-section">
      <div className="lp-modules-pill" style={{ margin: "0 auto 16px" }}>
        <span className="lp-tag-dot" />
        ROI Calculator
      </div>
      <h2 className="lp-modules-headline">How much could you save?</h2>
      <p className="lp-modules-sub">Adjust the sliders to your ED's parameters and see your estimated annual impact.</p>

      <div className="roi-layout">
        <div className="roi-inputs">
          <Slider label="ED Beds" value={beds} min={10} max={300} unit=" beds" onChange={setBeds} />
          <Slider label="Daily Patient Volume" value={dailyVolume} min={20} max={500} unit="/day" onChange={setDailyVolume} />
          <Slider label="Current Avg Wait Time" value={currentWait} min={15} max={200} unit=" min" onChange={setCurrentWait} />
          <Slider label="Current LWBS Rate" value={lwbsRate} min={0.5} max={12} step={0.5} unit="%" onChange={setLwbsRate} />
        </div>

        <div className="roi-results">
          <div className="roi-total">
            <div className="roi-total-label">Estimated Annual Savings</div>
            <div className="roi-total-val">${(totalSavings / 1e6).toFixed(1)}M</div>
          </div>
          <div className="roi-breakdown">
            {[
              ["LWBS Revenue Recovered", lwbsRevenue, `${lwbsReduced.toLocaleString()} patients retained`],
              ["Readmission Cost Averted", readmissionSavings, `${readmissionsAverted} readmissions prevented`],
              ["ED Diversion Savings", diversionSavings, `${edDiverted.toLocaleString()} patients routed to lower acuity`],
            ].map(([label, val, sub]) => (
              <div key={label} className="roi-line">
                <div>
                  <div className="roi-line-label">{label}</div>
                  <div className="roi-line-sub">{sub}</div>
                </div>
                <div className="roi-line-val">${(val / 1000).toFixed(0)}k</div>
              </div>
            ))}
          </div>
          <div className="roi-disclaimer">
            Estimates based on published ED benchmark data. Actual results vary.
          </div>
        </div>
      </div>
    </div>
  );
}

function PricingSection({ onBookDemo }) {
  return (
    <div className="pricing-section">
      <div className="lp-modules-pill" style={{ margin: "0 auto 16px" }}>
        <span className="lp-tag-dot" />
        Pricing
      </div>
      <h2 className="lp-modules-headline">Simple, transparent pricing</h2>
      <p className="lp-modules-sub">No per-seat fees. No hidden costs. Cancel anytime.</p>

      <div className="pricing-grid">
        {PRICING_TIERS.map(tier => (
          <div key={tier.name} className={`pricing-card ${tier.highlight ? "highlight" : ""}`}
            style={tier.highlight ? { borderColor: tier.color } : {}}>
            {tier.highlight && <div className="pricing-popular">Most Popular</div>}
            <div className="pricing-name" style={{ color: tier.color }}>{tier.name}</div>
            <div className="pricing-price">
              <span className="pricing-amount">{tier.price}</span>
              <span className="pricing-period">{tier.period}</span>
            </div>
            <div className="pricing-beds">{tier.beds}</div>
            <ul className="pricing-features">
              {tier.features.map(f => (
                <li key={f}>
                  <span style={{ color: tier.color }}>✓</span> {f}
                </li>
              ))}
            </ul>
            <button
              className="pricing-cta"
              style={tier.highlight ? { background: tier.color } : { borderColor: tier.color, color: tier.color }}
              onClick={onBookDemo}
            >
              {tier.cta}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function BookDemoModal({ onClose }) {
  const [form, setForm] = useState({ name: "", hospital: "", role: "", email: "", bed_count: "", message: "" });
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.hospital) { setError("Name, email, and hospital are required."); return; }
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/demo-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, bed_count: form.bed_count ? Number(form.bed_count) : null }),
      });
      const json = await res.json();
      if (json.success) setSuccess(true);
      else setError("Submission failed. Please try again.");
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="demo-modal-overlay" onClick={onClose}>
      <div className="demo-modal" onClick={e => e.stopPropagation()}>
        <div className="demo-modal-header">
          <div>
            <h2 className="demo-modal-title">Book a Demo</h2>
            <p className="demo-modal-sub">We'll reach out within 24 hours to schedule a personalized walkthrough.</p>
          </div>
          <button className="demo-modal-close" onClick={onClose}>✕</button>
        </div>

        {success ? (
          <div className="demo-success">
            <div className="demo-success-icon">✓</div>
            <h3>Request Received!</h3>
            <p>We'll be in touch within 24 hours to schedule your demo.</p>
            <button className="lp-nav-cta" style={{ marginTop: 16 }} onClick={onClose}>Close</button>
          </div>
        ) : (
          <form onSubmit={submit} className="demo-form">
            <div className="demo-form-row">
              <div className="form-group">
                <label>Full Name *</label>
                <input placeholder="Dr. Jane Smith" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div className="form-group">
                <label>Email *</label>
                <input type="email" placeholder="jane@hospital.org" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
              </div>
            </div>
            <div className="demo-form-row">
              <div className="form-group">
                <label>Hospital / Health System *</label>
                <input placeholder="General Hospital" value={form.hospital} onChange={e => setForm(f => ({ ...f, hospital: e.target.value }))} />
              </div>
              <div className="form-group">
                <label>Your Role</label>
                <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
                  <option value="">Select…</option>
                  {["CMO / CMIO", "ED Medical Director", "Charge Nurse / CNO", "IT / CIO", "Operations", "Other"].map(r => <option key={r}>{r}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Approximate Bed Count</label>
              <input type="number" placeholder="e.g. 50" value={form.bed_count} onChange={e => setForm(f => ({ ...f, bed_count: e.target.value }))} />
            </div>
            <div className="form-group">
              <label>Anything you'd like us to know?</label>
              <textarea rows={3} placeholder="Current pain points, integration requirements, timeline…"
                value={form.message} onChange={e => setForm(f => ({ ...f, message: e.target.value }))} />
            </div>
            {error && <div className="login-error">{error}</div>}
            <button type="submit" className="scan-btn" disabled={submitting} style={{ width: "100%" }}>
              {submitting ? "Submitting…" : "Request Demo →"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default function LoginPage() {
  const { login } = useAuth();
  const [stats, setStats] = useState(null);
  const [form, setForm] = useState({ username: "", password: "", totp_code: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [showDemoModal, setShowDemoModal] = useState(false);
  const modulesRef = useRef(null);
  const pricingRef = useRef(null);

  useEffect(() => {
    fetch(`${API_BASE}/stats`).then(r => r.ok ? r.json() : null).then(setStats).catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await login(form.username, form.password, mfaRequired ? form.totp_code : undefined);
      if (result?.mfa_required && !mfaRequired) setMfaRequired(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const openDemo = useCallback(() => setShowDemoModal(true), []);

  return (
    <div className="lp-root">
      {showDemoModal && <BookDemoModal onClose={() => setShowDemoModal(false)} />}

      {/* ── Top nav ── */}
      <nav className="lp-nav">
        <div className="lp-nav-brand">
          <span className="lp-nav-icon">⚕</span>
          <span className="lp-nav-name">MediScan</span>
          <span className="lp-nav-badge">Gateway v2</span>
        </div>
        <div className="lp-nav-links">
          <a href="#modules" onClick={e => { e.preventDefault(); modulesRef.current?.scrollIntoView({ behavior: "smooth" }); }}>Platform</a>
          <a href="#pricing" onClick={e => { e.preventDefault(); pricingRef.current?.scrollIntoView({ behavior: "smooth" }); }}>Pricing</a>
          <a href="/check" target="_blank" rel="noopener noreferrer">CareNavigator</a>
          <a href="/lobby" target="_blank" rel="noopener noreferrer">Lobby Display</a>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="lp-nav-demo-btn" onClick={openDemo}>Book Demo</button>
          <a href="#login" className="lp-nav-cta" onClick={e => { e.preventDefault(); document.getElementById("lp-login-form")?.scrollIntoView({ behavior: "smooth" }); }}>
            Sign In →
          </a>
        </div>
      </nav>

      {/* ── Hero ── */}
      <div className="lp-hero">
        {/* Left */}
        <div className="lp-hero-left">
          <div className="lp-hero-pill">AI-Native Emergency Triage Platform</div>
          <h1 className="lp-hero-headline">
            The MediScan<br />
            <span className="lp-headline-teal">Gateway</span> Platform
          </h1>
          <p className="lp-hero-sub">
            Six AI-native modules that unify walk-through triage, symptom routing,
            clinical documentation, post-discharge monitoring, and outcomes analytics
            into one seamless patient access platform.
          </p>

          <div className="lp-hero-stats">
            {[
              [stats?.patients_triaged?.toLocaleString() ?? "3,847+", "Patients Triaged"],
              [stats ? `${stats.ai_accuracy_pct}%` : "95.3%", "AI Accuracy"],
              [stats ? `${stats.door_to_triage_seconds_avg}s` : "14s", "Door-to-Triage"],
              [stats ? `${stats.uptime_pct}%` : "99.97%", "Uptime SLA"],
            ].map(([val, label]) => (
              <div key={label} className="lp-hero-stat">
                <div className="lp-hero-stat-val">{val}</div>
                <div className="lp-hero-stat-label">{label}</div>
              </div>
            ))}
          </div>

          <div className="lp-trust-badges">
            {["✓ HIPAA Compliant", "✓ BAA Available", "✓ SOC 2 In Progress", "🔒 E2E Encrypted"].map(b => (
              <span key={b} className="lp-trust-badge">{b}</span>
            ))}
          </div>

          <div style={{ display: "flex", gap: 12, marginBottom: 28 }}>
            <button className="lp-hero-cta-primary" onClick={openDemo}>Book a Demo →</button>
            <a href="#modules" className="lp-hero-cta-secondary"
              onClick={e => { e.preventDefault(); modulesRef.current?.scrollIntoView({ behavior: "smooth" }); }}>
              See Platform ↓
            </a>
          </div>

          <div className="lp-demo-section">
            <div className="lp-demo-label">Live Demo — no login required</div>
            <KioskDemo />
          </div>
        </div>

        {/* Right — login */}
        <div className="lp-hero-right" id="lp-login-form">
          <div className="lp-login-card">
            <h2 className="lp-login-title">Sign In</h2>
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
                </div>
              )}
              {error && <div className="login-error">{error}</div>}
              <button type="submit" className="scan-btn" disabled={loading} style={{ width: "100%", marginTop: 4 }}>
                {loading ? <><span className="btn-spinner" /> Signing in…</> : mfaRequired ? "Verify Code →" : "Sign In →"}
              </button>
            </form>

            <div className="lp-demo-creds">
              <div className="lp-creds-label">Demo credentials</div>
              {[["admin", "mediscan2026"], ["nurse", "nurse2026"], ["physician", "physician2026"]].map(([u, p]) => (
                <div key={u} className="lp-cred-row">
                  <code className="lp-cred-user">{u}</code>
                  <code className="lp-cred-pass">{p}</code>
                  <button className="lp-cred-fill" onClick={() => setForm(f => ({ ...f, username: u, password: p }))}>
                    Fill
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Partner logos ── */}
      <div className="lp-partners">
        {PARTNERS.map(p => (
          <div key={p} className="lp-partner-pill">{p}</div>
        ))}
      </div>

      {/* ── Platform modules ── */}
      <div className="lp-modules-section" ref={modulesRef}>
        <div className="lp-modules-pill">
          <span className="lp-tag-dot" style={{ background: "#0d9488" }} />
          Platform modules
        </div>
        <h2 className="lp-modules-headline">The MediScan platform</h2>
        <p className="lp-modules-sub">
          Six AI-native modules that unify triage, routing, documentation,
          follow-up, and analytics into one seamless ED platform.
        </p>
        <div className="lp-modules-grid">
          {MODULES.map(mod => <ModuleCard key={mod.title} mod={mod} />)}
        </div>
      </div>

      {/* ── ROI Calculator ── */}
      <ROICalculator />

      {/* ── Pricing ── */}
      <div ref={pricingRef}>
        <PricingSection onBookDemo={openDemo} />
      </div>

      {/* ── Outcomes strip ── */}
      <div className="lp-outcomes-strip">
        {[
          ["<15s", "Door-to-Triage", "vs 28 min national avg"],
          ["60%", "LWBS Reduction", "left without being seen"],
          ["94%", "Sepsis Detection", "vs 60% national avg"],
          ["$14.5k", "Readmission Cost Averted", "per escalated journey"],
          ["67%", "ED Diversion Rate", "via CareNavigator routing"],
          ["99.97%", "Platform Uptime", "SLA guaranteed"],
        ].map(([val, label, sub]) => (
          <div key={label} className="lp-outcome-item">
            <div className="lp-outcome-val">{val}</div>
            <div className="lp-outcome-label">{label}</div>
            <div className="lp-outcome-sub">{sub}</div>
          </div>
        ))}
      </div>

      {/* ── Footer ── */}
      <footer className="lp-footer">
        <span>⚕ MediScan Gateway v2</span>
        <span>Built with Claude claude-sonnet-4-6</span>
        <span>HIPAA · BAA · SOC 2</span>
      </footer>
    </div>
  );
}
