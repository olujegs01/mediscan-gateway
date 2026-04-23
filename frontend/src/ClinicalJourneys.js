import { useState, useEffect, useCallback } from "react";
import { API_BASE, useAuth } from "./AuthContext";

const STATUS_CONFIG = {
  active:    { color: "#0284c7", bg: "#eff6ff", label: "Active",    icon: "🔵" },
  escalated: { color: "#dc2626", bg: "#fef2f2", label: "Escalated", icon: "🚨" },
  completed: { color: "#16a34a", bg: "#f0fdf4", label: "Completed", icon: "✅" },
  pending:   { color: "#ca8a04", bg: "#fefce8", label: "Pending",   icon: "⏳" },
};

const ACTION_LABELS = {
  notify_attending:       "Notify Attending",
  page_charge_nurse:      "Page Charge Nurse",
  activate_rapid_response:"Rapid Response",
  notify_bed_management:  "Bed Management",
  proactive_rounding:     "Proactive Rounding",
  activate_surge_protocol:"Surge Protocol",
};

function JourneyRow({ journey, onCheckin, onResolve, checkinLoading, resolveLoading }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = STATUS_CONFIG[journey.journey_status] || STATUS_CONFIG.active;

  const nextCheckin = journey.next_checkin_at
    ? new Date(journey.next_checkin_at)
    : null;
  const isPast = nextCheckin && nextCheckin < new Date();
  const dischargedAgo = journey.discharge_at
    ? Math.round((Date.now() - new Date(journey.discharge_at)) / 3600000)
    : null;

  return (
    <div className={`journey-row ${journey.journey_status}`}>
      <div className="journey-row-main" onClick={() => setExpanded(e => !e)}>
        <div className="journey-status-dot" style={{ background: cfg.color }} />

        <div className="journey-info">
          <div className="journey-name">{journey.name}</div>
          <div className="journey-meta">
            ESI {journey.esi_level}
            {dischargedAgo != null && ` · Discharged ${dischargedAgo}h ago`}
            {journey.phone && ` · ${journey.phone}`}
          </div>
        </div>

        <div className="journey-checkin-progress">
          <div className="journey-checkin-dots">
            {Array.from({ length: journey.checkins_total }).map((_, i) => (
              <div
                key={i}
                className={`checkin-dot ${i < journey.checkins_completed ? "done" : ""}`}
              />
            ))}
          </div>
          <div className="journey-checkin-label">
            {journey.checkins_completed}/{journey.checkins_total} check-ins
          </div>
        </div>

        <div className="journey-badge" style={{ background: cfg.bg, color: cfg.color }}>
          {cfg.icon} {cfg.label}
        </div>

        {nextCheckin && (
          <div className={`journey-next ${isPast ? "overdue" : ""}`}>
            {isPast ? "⚠ Overdue" : `Next: ${nextCheckin.toLocaleDateString()} ${nextCheckin.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`}
          </div>
        )}

        <div className="journey-chevron">{expanded ? "▲" : "▼"}</div>
      </div>

      {expanded && (
        <div className="journey-detail">
          {journey.escalated_reason && (
            <div className="journey-escalation-alert">
              <strong>🚨 Escalation reason:</strong> {journey.escalated_reason}
            </div>
          )}

          {journey.last_response && (
            <div className="journey-last-response">
              <strong>Last response:</strong> "{journey.last_response}"
              {journey.last_checkin_at && (
                <span className="journey-response-time">
                  {" "}· {new Date(journey.last_checkin_at).toLocaleString()}
                </span>
              )}
            </div>
          )}

          {journey.checkin_log?.length > 0 && (
            <div className="journey-log">
              <div className="journey-log-title">Check-in Log</div>
              {journey.checkin_log.slice().reverse().map((entry, i) => (
                <div key={i} className={`journey-log-entry ${entry.worsening ? "worsening" : ""}`}>
                  <span className="log-time">{new Date(entry.timestamp).toLocaleString()}</span>
                  {entry.type === "checkin_sent"
                    ? <span>SMS sent (check-in #{entry.checkin_num}) — {entry.sms_sent ? "Delivered" : "Failed"}</span>
                    : <span>Patient replied: "{entry.message}" {entry.worsening ? "⚠ Worsening" : "✓ Stable"}</span>
                  }
                </div>
              ))}
            </div>
          )}

          <div className="journey-actions">
            {journey.journey_status !== "completed" && (
              <button
                className="journey-btn primary"
                onClick={() => onCheckin(journey.journey_id)}
                disabled={checkinLoading}
              >
                {checkinLoading ? "Sending…" : "📤 Send Check-in Now"}
              </button>
            )}
            {journey.journey_status === "escalated" && (
              <button
                className="journey-btn warning"
                onClick={() => onResolve(journey.journey_id)}
                disabled={resolveLoading}
              >
                {resolveLoading ? "Resolving…" : "✓ Mark Resolved"}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function CompliancePage({ token }) {
  const [status, setStatus] = useState(null);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/compliance/status`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
      fetch(`${API_BASE}/compliance/escalation-rules`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
    ]).then(([s, r]) => {
      setStatus(s);
      setRules(Array.isArray(r) ? r : []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [token]);

  const toggleRule = async (ruleId, enabled) => {
    setSaving(ruleId);
    const res = await fetch(`${API_BASE}/compliance/escalation-rules/${ruleId}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    if (res.ok) {
      const updated = await res.json();
      setRules(r => r.map(x => x.id === ruleId ? updated : x));
    }
    setSaving(null);
  };

  const downloadBAA = () => {
    window.open(`${API_BASE}/compliance/baa`, "_blank");
  };

  if (loading) return <div className="page-loading">Loading compliance data…</div>;

  const passCount = status?.controls_passing || 0;
  const total = status?.controls_total || 1;
  const pct = status?.compliance_score_pct || 0;

  return (
    <div className="compliance-page">
      {/* Score header */}
      <div className="compliance-hero">
        <div className="compliance-score-ring">
          <svg viewBox="0 0 36 36" className="circular-chart">
            <path className="circle-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
            <path
              className="circle"
              strokeDasharray={`${pct}, 100`}
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
            <text x="18" y="20.35" className="percentage">{pct}%</text>
          </svg>
        </div>
        <div className="compliance-score-info">
          <h2>HIPAA Compliance Score</h2>
          <p>{passCount} of {total} controls passing</p>
          <div className="compliance-badges">
            <span className="comp-badge hipaa">HIPAA Compliant</span>
            <span className="comp-badge soc2">SOC 2 — In Progress</span>
            <span className="comp-badge baa" onClick={downloadBAA} style={{ cursor: "pointer" }}>
              📄 Download BAA
            </span>
          </div>
        </div>
      </div>

      {/* Controls grid */}
      <div className="section-title">HIPAA Controls</div>
      <div className="compliance-controls">
        {status?.hipaa_controls?.map((ctrl, i) => (
          <div key={i} className={`control-row ${ctrl.status}`}>
            <span className="control-icon">
              {ctrl.status === "pass" ? "✅" : ctrl.status === "in_progress" ? "🔄" : ctrl.status === "scheduled" ? "📅" : "📋"}
            </span>
            <span className="control-text">{ctrl.control}</span>
            <span className={`control-badge ${ctrl.status}`}>
              {ctrl.status === "pass" ? "Pass" : ctrl.status === "in_progress" ? "In Progress" : ctrl.status === "scheduled" ? "Scheduled" : "Available"}
            </span>
          </div>
        ))}
      </div>

      {/* Data retention */}
      {status?.data_retention && (
        <>
          <div className="section-title" style={{ marginTop: 28 }}>Data Retention Policy</div>
          <div className="compliance-table">
            {[
              ["Patient Records", `${status.data_retention.patient_records_years} years`],
              ["Audit Logs", `${status.data_retention.audit_logs_years} years`],
              ["SOAP Notes", `${status.data_retention.soap_notes_years} years`],
              ["Shift Reports", `${status.data_retention.shift_reports_years} years`],
              ["Backup Retention", `${status.data_retention.backup_retention_days} days`],
              ["Deletion Method", status.data_retention.deletion_method],
            ].map(([label, val]) => (
              <div key={label} className="compliance-table-row">
                <span className="ct-label">{label}</span>
                <span className="ct-val">{val}</span>
              </div>
            ))}
            <div className="compliance-table-row basis">
              <span className="ct-label">Legal Basis</span>
              <span className="ct-val">{status.data_retention.basis}</span>
            </div>
          </div>
        </>
      )}

      {/* Escalation rules */}
      <div className="section-title" style={{ marginTop: 28 }}>Escalation Rules</div>
      <p className="section-sub">Configure automatic escalation triggers. Changes take effect immediately.</p>
      <div className="escalation-rules">
        {rules.map(rule => (
          <div key={rule.id} className={`esc-rule ${rule.enabled ? "enabled" : "disabled"}`}>
            <div className="esc-rule-main">
              <div className="esc-rule-info">
                <div className="esc-rule-name">{rule.rule_name}</div>
                <div className="esc-rule-meta">
                  Action: <strong>{ACTION_LABELS[rule.action] || rule.action}</strong>
                  {" · "}Response time: <strong>{rule.response_time_minutes} min</strong>
                </div>
              </div>
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  checked={rule.enabled}
                  disabled={saving === rule.id}
                  onChange={e => toggleRule(rule.id, e.target.checked)}
                />
                <span className="toggle-slider" />
              </label>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ClinicalJourneys({ activeTab }) {
  const { user } = useAuth();
  const token = user?.token;
  const [journeys, setJourneys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const load = useCallback(() => {
    const url = filter === "all"
      ? `${API_BASE}/journeys`
      : `${API_BASE}/journeys?status=${filter}`;
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(data => { setJourneys(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token, filter]);

  useEffect(() => { load(); }, [load]);

  const [checkinLoading, setCheckinLoading] = useState(null);
  const [resolveLoading, setResolveLoading] = useState(null);
  const [toast, setToast] = useState(null);

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 4000);
  };

  const handleCheckin = async (journeyId) => {
    setCheckinLoading(journeyId);
    try {
      const res = await fetch(`${API_BASE}/journeys/${journeyId}/checkin`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.sms_sent ? "SMS check-in sent to patient." : "Check-in logged (SMS not configured).", true);
      } else {
        showToast(data.detail || "Check-in failed.", false);
      }
      load();
    } catch {
      showToast("Network error — please retry.", false);
    } finally {
      setCheckinLoading(null);
    }
  };

  const handleResolve = async (journeyId) => {
    setResolveLoading(journeyId);
    try {
      const res = await fetch(`${API_BASE}/journeys/${journeyId}/resolve`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        showToast("Journey resolved and marked completed.", true);
      } else {
        showToast("Failed to resolve journey.", false);
      }
      load();
    } catch {
      showToast("Network error — please retry.", false);
    } finally {
      setResolveLoading(null);
    }
  };

  if (activeTab === "compliance") return <CompliancePage token={token} />;

  const escalated = journeys.filter(j => j.journey_status === "escalated");
  const active    = journeys.filter(j => j.journey_status === "active");
  const completed = journeys.filter(j => j.journey_status === "completed");

  const filtered = filter === "all" ? journeys
    : filter === "escalated" ? escalated
    : filter === "active" ? active
    : completed;

  return (
    <div className="journeys-page">
      {toast && (
        <div style={{
          position: "fixed", top: 20, right: 20, zIndex: 9999,
          padding: "12px 20px", borderRadius: 10, fontSize: 13, fontWeight: 600,
          background: toast.ok ? "rgba(34,197,94,0.15)" : "rgba(220,38,38,0.15)",
          border: `1px solid ${toast.ok ? "rgba(34,197,94,0.4)" : "rgba(220,38,38,0.4)"}`,
          color: toast.ok ? "#4ade80" : "#f87171",
          boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
        }}>
          {toast.ok ? "✓" : "✗"} {toast.msg}
        </div>
      )}
      {/* Summary cards */}
      <div className="journey-summary-cards">
        {[
          { label: "Active Journeys",  value: active.length,    color: "#0284c7", icon: "🔵" },
          { label: "Escalated",        value: escalated.length, color: "#dc2626", icon: "🚨" },
          { label: "Completed",        value: completed.length, color: "#16a34a", icon: "✅" },
          { label: "Total",            value: journeys.length,  color: "#6b7280", icon: "📋" },
        ].map(card => (
          <div key={card.label} className="journey-summary-card">
            <div className="jsc-icon">{card.icon}</div>
            <div className="jsc-value" style={{ color: card.color }}>{card.value}</div>
            <div className="jsc-label">{card.label}</div>
          </div>
        ))}
      </div>

      {/* Filter tabs */}
      <div className="journey-filter-tabs">
        {["all", "escalated", "active", "completed"].map(f => (
          <button
            key={f}
            className={`journey-filter-tab ${filter === f ? "active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f === "all" ? "All" : STATUS_CONFIG[f]?.icon + " " + STATUS_CONFIG[f]?.label}
            {f === "escalated" && escalated.length > 0 && (
              <span className="journey-badge-count">{escalated.length}</span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="page-loading">Loading journeys…</div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🩺</div>
          <div className="empty-title">No {filter === "all" ? "" : filter} journeys yet</div>
          <div className="empty-sub">Journeys are triggered automatically when patients are discharged with a phone number on file.</div>
        </div>
      ) : (
        <div className="journey-list">
          {filtered.map(j => (
            <JourneyRow
              key={j.journey_id}
              journey={j}
              onCheckin={handleCheckin}
              onResolve={handleResolve}
              checkinLoading={checkinLoading === j.journey_id}
              resolveLoading={resolveLoading === j.journey_id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
