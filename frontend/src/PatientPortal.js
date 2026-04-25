import { useState, useEffect } from "react";
import { API_BASE } from "./AuthContext";
import "./PatientPortal.css";

const ESI_LABEL = { 1: "Critical", 2: "High Acuity", 3: "Urgent", 4: "Less Urgent", 5: "Non-Urgent" };
const ESI_COLOR = { 1: "#dc2626", 2: "#ea580c", 3: "#ca8a04", 4: "#16a34a", 5: "#6b7280" };
const STATUS_CONFIG = {
  active:    { label: "Active",    color: "#0d9488", bg: "rgba(13,148,136,0.1)" },
  completed: { label: "Completed", color: "#22c55e", bg: "rgba(34,197,94,0.1)"  },
  escalated: { label: "Escalated — Staff Notified", color: "#dc2626", bg: "rgba(220,38,38,0.1)" },
};

export default function PatientPortal() {
  const token = new URLSearchParams(window.location.search).get("token");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [response, setResponse] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [feedback, setFeedback] = useState({ rating: 0, comment: "", category: "overall" });
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  useEffect(() => {
    if (!token) { setError("Invalid portal link."); setLoading(false); return; }
    fetch(`${API_BASE}/patient/portal/${token}`)
      .then(r => {
        if (!r.ok) throw new Error("Portal link not found or expired.");
        return r.json();
      })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [token]);

  const submitFeedback = async () => {
    if (!feedback.rating) return;
    setFeedbackSubmitting(true);
    try {
      await fetch(`${API_BASE}/journeys/${data.id}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(feedback),
      });
      setFeedbackSubmitted(true);
    } catch {
      alert("Failed to submit feedback. Please try again.");
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const submitResponse = async () => {
    if (!response.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/patient/portal/${token}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ response: response.trim() }),
      });
      const json = await res.json();
      setSubmitted(true);
      setData(d => ({ ...d, journey_status: json.escalated ? "escalated" : d.journey_status }));
    } catch {
      alert("Failed to submit. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return (
    <div className="pp-root pp-center">
      <div className="pp-spinner" />
      <p>Loading your care portal…</p>
    </div>
  );

  if (error) return (
    <div className="pp-root pp-center">
      <div className="pp-error-icon">⚠️</div>
      <h2>Link Not Found</h2>
      <p>{error}</p>
      <p className="pp-muted">If you need assistance, call us or visit your nearest urgent care.</p>
    </div>
  );

  const esiColor = ESI_COLOR[data.esi_level] || "#94a3b8";
  const statusCfg = STATUS_CONFIG[data.journey_status] || STATUS_CONFIG.active;

  return (
    <div className="pp-root">
      <header className="pp-header">
        <div className="pp-brand">
          <span>⚕</span> MediScan Patient Portal
        </div>
        <div className="pp-secure-badge">🔒 HIPAA Secure</div>
      </header>

      <main className="pp-main">
        {/* ── Patient hero ── */}
        <div className="pp-hero-card">
          <div className="pp-greeting">Hello, {data.name.split(" ")[0]}</div>
          <div className="pp-subgreeting">Here's your post-discharge care summary.</div>
          <div className="pp-esi-row">
            <span className="pp-esi-badge" style={{ background: esiColor }}>
              ESI {data.esi_level} — {ESI_LABEL[data.esi_level]}
            </span>
            <span className="pp-status-badge" style={{ color: statusCfg.color, background: statusCfg.bg }}>
              {statusCfg.label}
            </span>
          </div>
          {data.discharge_at && (
            <div className="pp-discharge-date">
              Discharged: {new Date(data.discharge_at).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
            </div>
          )}
        </div>

        {/* ── Escalation banner ── */}
        {data.journey_status === "escalated" && (
          <div className="pp-alert-banner">
            🚨 <strong>A care team member has been notified</strong> about your worsening symptoms.
            If you are in immediate danger, call <strong>911</strong>.
            <div className="pp-alert-reason">{data.escalated_reason}</div>
          </div>
        )}

        {/* ── Check-in progress ── */}
        <div className="pp-card">
          <h3 className="pp-card-title">Follow-up Check-ins</h3>
          <div className="pp-checkin-track">
            {Array.from({ length: data.checkins_total || 2 }).map((_, i) => {
              const done = i < (data.checkins_completed || 0);
              return (
                <div key={i} className={`pp-checkin-dot ${done ? "done" : "pending"}`}>
                  <div className="pp-dot-circle">{done ? "✓" : i + 1}</div>
                  <div className="pp-dot-label">Check-in {i + 1}</div>
                </div>
              );
            })}
          </div>
          {data.last_response && (
            <div className="pp-last-response">
              <span className="pp-response-label">Your last response:</span>
              <span className="pp-response-text">"{data.last_response}"</span>
            </div>
          )}
        </div>

        {/* ── Upcoming check-ins ── */}
        {data.upcoming_checkins?.length > 0 && (
          <div className="pp-card">
            <h3 className="pp-card-title">Upcoming Check-ins</h3>
            {data.upcoming_checkins.map(c => (
              <div key={c.checkin_num} className="pp-upcoming-row">
                <div className="pp-upcoming-num">#{c.checkin_num}</div>
                <div>
                  <div className="pp-upcoming-date">
                    {new Date(c.due_at).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
                    {" at "}
                    {new Date(c.due_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
                  </div>
                  <div className="pp-upcoming-sub">{c.hours_post_discharge}h post-discharge</div>
                </div>
                <div className="pp-upcoming-status">SMS + Portal</div>
              </div>
            ))}
          </div>
        )}

        {/* ── Submit a response ── */}
        {data.journey_status === "active" && !submitted && (
          <div className="pp-card pp-response-card">
            <h3 className="pp-card-title">How are you feeling today?</h3>
            <p className="pp-response-hint">
              Rate your symptoms or describe how you're doing. Reply "worse" or describe
              emergency symptoms to alert your care team immediately.
            </p>
            <div className="pp-quick-replies">
              {["Feeling much better", "About the same", "A little worse", "Much worse — need help"].map(opt => (
                <button
                  key={opt}
                  className={`pp-quick-btn ${response === opt ? "selected" : ""}`}
                  onClick={() => setResponse(opt)}
                >
                  {opt}
                </button>
              ))}
            </div>
            <textarea
              className="pp-textarea"
              placeholder="Or describe your symptoms in detail…"
              value={response}
              onChange={e => setResponse(e.target.value)}
              rows={3}
            />
            <button
              className="pp-submit-btn"
              onClick={submitResponse}
              disabled={submitting || !response.trim()}
            >
              {submitting ? "Sending…" : "Submit Response →"}
            </button>
          </div>
        )}

        {submitted && (
          <div className="pp-card pp-success-card">
            <div className="pp-success-icon">✓</div>
            <div className="pp-success-title">Response Received</div>
            <div className="pp-success-sub">
              Your care team has been notified. If your symptoms worsen, call 911 or return to the ED.
            </div>
          </div>
        )}

        {/* ── Check-in history ── */}
        {data.checkin_log?.length > 0 && (
          <div className="pp-card">
            <h3 className="pp-card-title">Check-in History</h3>
            {[...data.checkin_log].reverse().map((log, i) => (
              <div key={i} className="pp-log-row">
                <div className="pp-log-time">
                  {new Date(log.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  {" "}
                  {new Date(log.timestamp).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
                </div>
                <div className="pp-log-content">
                  {log.type === "checkin_sent" ? (
                    <span className="pp-log-sent">Check-in SMS sent</span>
                  ) : (
                    <span className={`pp-log-response ${log.worsening ? "worsening" : ""}`}>
                      {log.worsening && "⚠️ "}{log.message}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Patient feedback ── */}
        {!feedbackSubmitted ? (
          <div className="pp-card">
            <h3 className="pp-card-title">Rate Your Experience</h3>
            <p style={{ fontSize: 13, color: "#64748b", marginBottom: 12 }}>
              Help us improve care for future patients.
            </p>
            <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
              {[1, 2, 3, 4, 5].map(s => (
                <button key={s} onClick={() => setFeedback(f => ({ ...f, rating: s }))}
                  style={{
                    flex: 1, padding: "8px 0", borderRadius: 8, border: "1px solid",
                    borderColor: feedback.rating >= s ? "#0d9488" : "#1e293b",
                    background: feedback.rating >= s ? "rgba(13,148,136,0.15)" : "transparent",
                    color: feedback.rating >= s ? "#5eead4" : "#475569",
                    fontSize: 18, cursor: "pointer", transition: "all 0.15s",
                  }}>★</button>
              ))}
            </div>
            <select value={feedback.category} onChange={e => setFeedback(f => ({ ...f, category: e.target.value }))}
              style={{ width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid #1e293b", background: "#0d1b2e", color: "#e2e8f0", marginBottom: 10, fontSize: 13 }}>
              <option value="overall">Overall Experience</option>
              <option value="wait_time">Wait Time</option>
              <option value="staff">Staff & Communication</option>
              <option value="communication">Follow-up Communication</option>
            </select>
            <textarea rows={3} placeholder="Optional comment…"
              value={feedback.comment} onChange={e => setFeedback(f => ({ ...f, comment: e.target.value }))}
              style={{ width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid #1e293b", background: "#0d1b2e", color: "#e2e8f0", fontSize: 13, resize: "vertical", boxSizing: "border-box", marginBottom: 10 }}
            />
            <button onClick={submitFeedback} disabled={!feedback.rating || feedbackSubmitting}
              style={{ width: "100%", padding: "10px 0", borderRadius: 8, background: feedback.rating ? "#0d9488" : "#1e293b", color: feedback.rating ? "white" : "#475569", border: "none", cursor: feedback.rating ? "pointer" : "not-allowed", fontWeight: 600, fontSize: 14 }}>
              {feedbackSubmitting ? "Submitting…" : "Submit Feedback"}
            </button>
          </div>
        ) : (
          <div className="pp-card" style={{ textAlign: "center", padding: "24px 16px" }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>⭐</div>
            <div style={{ fontWeight: 700, color: "#4ade80", marginBottom: 6 }}>Thank You!</div>
            <div style={{ fontSize: 13, color: "#64748b" }}>Your feedback helps us improve care for every patient.</div>
          </div>
        )}

        {/* ── Care resources ── */}
        <div className="pp-card pp-resources-card">
          <h3 className="pp-card-title">Need Help?</h3>
          <div className="pp-resource-grid">
            <a href="tel:911" className="pp-resource-btn emergency">📞 Call 911</a>
            <a href="/check" target="_blank" rel="noopener noreferrer" className="pp-resource-btn care">
              🩺 Symptom Check
            </a>
          </div>
          <p className="pp-resource-note">
            If you are experiencing a medical emergency, call 911 immediately.
            For non-emergency questions, use the symptom checker above.
          </p>
        </div>
      </main>

      <footer className="pp-footer">
        ⚕ MediScan Gateway · HIPAA Compliant · All data encrypted in transit
      </footer>
    </div>
  );
}
