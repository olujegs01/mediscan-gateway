import { useState, useRef, useCallback, useEffect } from "react";
import "./SymptomCheck.css";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const RISK_FACTOR_OPTIONS = [
  "Diabetes", "Heart disease", "High blood pressure", "Asthma / COPD",
  "Cancer", "Pregnancy", "Kidney disease", "Stroke history",
  "Blood clots (DVT/PE)", "Immunocompromised", "Obesity", "Smoking",
];

const COMMON_SYMPTOMS = [
  "Chest pain", "Shortness of breath", "Severe headache", "Fever",
  "Abdominal pain", "Nausea / vomiting", "Dizziness", "Back pain",
  "Sore throat", "Cough", "Rash", "Joint pain", "Fatigue",
];

const LANGUAGE_OPTIONS = [
  "English", "Spanish", "French", "Portuguese", "Mandarin",
  "Arabic", "Hindi", "Russian", "Haitian Creole", "Vietnamese",
];

const CARE_LEVEL_CONFIG = {
  CALL_911:     { color: "#dc2626", bg: "#fef2f2", border: "#fca5a5", icon: "🚨", cta: "call" },
  ED_NOW:       { color: "#ea580c", bg: "#fff7ed", border: "#fdba74", icon: "🔴", cta: "ed" },
  ED_SOON:      { color: "#f97316", bg: "#fff7ed", border: "#fdba74", icon: "🟠", cta: "ed" },
  URGENT_CARE:  { color: "#ca8a04", bg: "#fefce8", border: "#fde047", icon: "🟡", cta: "urgent" },
  TELEHEALTH:   { color: "#0d9488", bg: "#f0fdfa", border: "#99f6e4", icon: "💻", cta: "telehealth" },
  PRIMARY_CARE: { color: "#16a34a", bg: "#f0fdf4", border: "#86efac", icon: "🩺", cta: "primary" },
  SELF_CARE:    { color: "#6b7280", bg: "#f9fafb", border: "#d1d5db", icon: "🏠", cta: "self" },
};

// ── Voice input hook ──────────────────────────────────────────────────────────
function useVoiceInput(onTranscript) {
  const recognitionRef = useRef(null);
  const [listening, setListening] = useState(false);
  const [supported] = useState(() => "webkitSpeechRecognition" in window || "SpeechRecognition" in window);

  const start = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    const r = new SR();
    r.continuous = false;
    r.interimResults = true;
    r.lang = "en-US";
    r.onstart = () => setListening(true);
    r.onend = () => setListening(false);
    r.onresult = (e) => {
      const transcript = Array.from(e.results).map(r => r[0].transcript).join(" ");
      if (e.results[e.results.length - 1].isFinal) {
        onTranscript(transcript);
      }
    };
    r.onerror = () => setListening(false);
    recognitionRef.current = r;
    r.start();
  }, [onTranscript]);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
  }, []);

  return { supported, listening, start, stop };
}

// ── Step components ───────────────────────────────────────────────────────────

function StepDemographics({ data, onChange, onNext }) {
  const valid = data.age >= 1 && data.age <= 120 && data.sex;
  return (
    <div className="sc-step">
      <div className="sc-step-header">
        <div className="sc-step-num">1</div>
        <div>
          <h2>About You</h2>
          <p>This helps us give you the most accurate assessment.</p>
        </div>
      </div>

      <div className="sc-field-row">
        <div className="sc-field">
          <label>Age</label>
          <div className="sc-age-group">
            <input
              type="range" min={1} max={110} value={data.age || 30}
              onChange={e => onChange("age", +e.target.value)}
              className="sc-slider"
            />
            <input
              type="number" min={1} max={120} value={data.age || ""}
              placeholder="—"
              onChange={e => onChange("age", +e.target.value)}
              className="sc-age-number"
            />
          </div>
          {data.age > 0 && <div className="sc-age-label">{data.age} years old</div>}
        </div>
      </div>

      <div className="sc-field">
        <label>Biological Sex</label>
        <div className="sc-radio-group">
          {["Male", "Female", "Other"].map(s => (
            <button
              key={s}
              className={`sc-radio-btn ${data.sex === s ? "selected" : ""}`}
              onClick={() => onChange("sex", s)}
              type="button"
            >
              {s === "Male" ? "♂ Male" : s === "Female" ? "♀ Female" : "⊕ Other"}
            </button>
          ))}
        </div>
      </div>

      <div className="sc-field">
        <label>Preferred Language</label>
        <select
          value={data.language}
          onChange={e => onChange("language", e.target.value)}
          className="sc-select"
        >
          {LANGUAGE_OPTIONS.map(l => <option key={l}>{l}</option>)}
        </select>
      </div>

      <div className="sc-field">
        <label>Known Health Conditions <span className="sc-optional">(optional)</span></label>
        <div className="sc-chips">
          {RISK_FACTOR_OPTIONS.map(rf => (
            <button
              key={rf}
              type="button"
              className={`sc-chip ${data.riskFactors.includes(rf) ? "selected" : ""}`}
              onClick={() => {
                const updated = data.riskFactors.includes(rf)
                  ? data.riskFactors.filter(x => x !== rf)
                  : [...data.riskFactors, rf];
                onChange("riskFactors", updated);
              }}
            >
              {rf}
            </button>
          ))}
        </div>
      </div>

      <button className="sc-btn-primary" onClick={onNext} disabled={!valid}>
        Continue →
      </button>
    </div>
  );
}

function StepSymptoms({ data, onChange, onNext }) {
  const onTranscript = useCallback(t => {
    onChange("symptoms", (data.symptoms ? data.symptoms + " " : "") + t);
  }, [data.symptoms, onChange]);

  const { supported, listening, start, stop } = useVoiceInput(onTranscript);

  const addChip = (chip) => {
    const txt = data.symptoms.trim();
    onChange("symptoms", txt ? `${txt}, ${chip.toLowerCase()}` : chip.toLowerCase());
  };

  return (
    <div className="sc-step">
      <div className="sc-step-header">
        <div className="sc-step-num">2</div>
        <div>
          <h2>Describe Your Symptoms</h2>
          <p>Be as specific as possible — when it started, severity, location.</p>
        </div>
      </div>

      <div className="sc-field">
        <label>What's bothering you?</label>
        <div className="sc-textarea-wrap">
          <textarea
            className="sc-textarea"
            placeholder="e.g. I have chest pain that started 2 hours ago, radiating to my left arm, rated 7/10 in severity..."
            value={data.symptoms}
            onChange={e => onChange("symptoms", e.target.value)}
            rows={5}
          />
          {supported && (
            <button
              type="button"
              className={`sc-voice-btn ${listening ? "active" : ""}`}
              onClick={listening ? stop : start}
              title={listening ? "Stop recording" : "Speak your symptoms"}
            >
              {listening ? (
                <><span className="sc-voice-pulse" />Stop</>
              ) : (
                <>🎤 Speak</>
              )}
            </button>
          )}
        </div>
      </div>

      <div className="sc-field">
        <label>Quick add</label>
        <div className="sc-chips">
          {COMMON_SYMPTOMS.map(s => (
            <button
              key={s}
              type="button"
              className="sc-chip"
              onClick={() => addChip(s)}
            >
              + {s}
            </button>
          ))}
        </div>
      </div>

      <div className="sc-disclaimer">
        <span>⚠️</span>
        <span>This is not a substitute for professional medical advice. If you are experiencing a life-threatening emergency, <strong>call 911 now</strong>.</span>
      </div>

      <button
        className="sc-btn-primary"
        onClick={onNext}
        disabled={!data.symptoms.trim() || data.symptoms.trim().length < 5}
      >
        Analyze Symptoms →
      </button>
    </div>
  );
}

function QuestionCard({ q, answer, onAnswer }) {
  if (q.type === "yesno") {
    return (
      <div className="sc-question-card">
        <p className="sc-q-text">{q.text}</p>
        <div className="sc-radio-group">
          {["Yes", "No"].map(opt => (
            <button
              key={opt}
              type="button"
              className={`sc-radio-btn ${answer === opt ? "selected" : ""}`}
              onClick={() => onAnswer(q.id, opt)}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>
    );
  }
  if (q.type === "scale") {
    return (
      <div className="sc-question-card">
        <p className="sc-q-text">{q.text}</p>
        <div className="sc-scale-group">
          {[1,2,3,4,5,6,7,8,9,10].map(n => (
            <button
              key={n}
              type="button"
              className={`sc-scale-btn ${answer === String(n) ? "selected" : ""}`}
              onClick={() => onAnswer(q.id, String(n))}
            >
              {n}
            </button>
          ))}
        </div>
        <div className="sc-scale-labels"><span>Mild</span><span>Severe</span></div>
      </div>
    );
  }
  if (q.type === "choice" && q.options?.length) {
    return (
      <div className="sc-question-card">
        <p className="sc-q-text">{q.text}</p>
        <div className="sc-choice-group">
          {q.options.map(opt => (
            <button
              key={opt}
              type="button"
              className={`sc-choice-btn ${answer === opt ? "selected" : ""}`}
              onClick={() => onAnswer(q.id, opt)}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>
    );
  }
  // text
  return (
    <div className="sc-question-card">
      <p className="sc-q-text">{q.text}</p>
      <input
        type="text"
        className="sc-input"
        placeholder="Type your answer..."
        value={answer || ""}
        onChange={e => onAnswer(q.id, e.target.value)}
      />
    </div>
  );
}

function StepQA({ preliminary, questions, answers, onAnswer, onSubmit, loading }) {
  const allAnswered = questions.every(q => answers[q.id]);
  return (
    <div className="sc-step">
      <div className="sc-step-header">
        <div className="sc-step-num">3</div>
        <div>
          <h2>A Few Quick Questions</h2>
          {preliminary && <p className="sc-preliminary">{preliminary}</p>}
        </div>
      </div>

      {questions.map(q => (
        <QuestionCard
          key={q.id}
          q={q}
          answer={answers[q.id] || ""}
          onAnswer={onAnswer}
        />
      ))}

      <button
        className="sc-btn-primary"
        onClick={onSubmit}
        disabled={!allAnswered || loading}
      >
        {loading ? <><span className="sc-spinner" /> Analyzing...</> : "Get My Recommendation →"}
      </button>
    </div>
  );
}

function ActionButtons({ cta, careLevel, onPreRegister, onSchedule }) {
  if (cta === "call") return (
    <a href="tel:911" className="sc-action-btn emergency">
      🚨 Call 911 Now
    </a>
  );
  if (cta === "ed") return (
    <div className="sc-action-group">
      <button className="sc-action-btn primary" onClick={onPreRegister}>
        🏥 Pre-Register for ED
      </button>
      <a href="https://maps.google.com/?q=emergency+room+near+me" target="_blank" rel="noopener noreferrer" className="sc-action-btn secondary">
        📍 Find Nearest ED
      </a>
    </div>
  );
  if (cta === "urgent") return (
    <div className="sc-action-group">
      <button className="sc-action-btn primary" onClick={() => onSchedule("urgent_care")}>
        📅 Book Urgent Care Slot
      </button>
      <a href="https://maps.google.com/?q=urgent+care+near+me" target="_blank" rel="noopener noreferrer" className="sc-action-btn secondary">
        📍 Walk-in Locations
      </a>
    </div>
  );
  if (cta === "telehealth") return (
    <div className="sc-action-group">
      <button className="sc-action-btn primary" onClick={() => onSchedule("telehealth")}>
        💻 Book Telehealth Visit
      </button>
    </div>
  );
  if (cta === "primary") return (
    <div className="sc-action-group">
      <button className="sc-action-btn primary" onClick={() => onSchedule("primary_care")}>
        📅 Book Doctor Appointment
      </button>
    </div>
  );
  return null;
}

// ── Scheduling step ───────────────────────────────────────────────────────────

function SlotCard({ slot, onBook, booking }) {
  const dateObj = new Date(`${slot.slot_date}T${slot.slot_time}`);
  const isToday = slot.slot_date === new Date().toISOString().split("T")[0];
  const isTomorrow = slot.slot_date === new Date(Date.now() + 86400000).toISOString().split("T")[0];
  const dayLabel = isToday ? "Today" : isTomorrow ? "Tomorrow" : dateObj.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });

  return (
    <div className={`sc-slot-card ${booking === slot.slot_id ? "booking" : ""}`}>
      <div className="sc-slot-time">
        <div className="sc-slot-day">{dayLabel}</div>
        <div className="sc-slot-hour">{dateObj.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
        <div className="sc-slot-duration">{slot.duration_min} min</div>
      </div>
      <div className="sc-slot-info">
        <div className="sc-slot-provider">{slot.provider_name}</div>
        <div className="sc-slot-specialty">{slot.specialty}</div>
        <div className="sc-slot-location">📍 {slot.location}</div>
        {slot.address && <div className="sc-slot-address">{slot.address}</div>}
      </div>
      <button
        className="sc-slot-book-btn"
        onClick={() => onBook(slot)}
        disabled={booking != null}
      >
        {booking === slot.slot_id ? <span className="sc-spinner" /> : "Book →"}
      </button>
    </div>
  );
}

function StepSchedule({ careType, demographicData, symptomsData, onDone, onSkip }) {
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [form, setForm] = useState({ name: "", phone: "" });
  const [formStep, setFormStep] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/check/slots?care_type=${careType}`)
      .then(r => r.json())
      .then(d => { setSlots(d.slots || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [careType]);

  const handleSlotSelect = (slot) => {
    setSelectedSlot(slot);
    setFormStep(true);
  };

  const handleBook = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { setError("Please enter your name"); return; }
    setBooking(selectedSlot.slot_id);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/check/schedule`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slot_id: selectedSlot.slot_id,
          patient_name: form.name.trim(),
          patient_age: demographicData.age,
          phone: form.phone.trim(),
          symptoms: symptomsData.symptoms,
        }),
      });
      if (!res.ok) throw new Error("Booking failed. Please try another slot.");
      const data = await res.json();
      setConfirmation(data);
    } catch (err) {
      setError(err.message);
      setBooking(null);
    }
  };

  const downloadIcal = () => {
    if (!confirmation?.calendar_event) return;
    const blob = new Blob([confirmation.calendar_event], { type: "text/calendar" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "appointment.ics";
    a.click();
  };

  if (confirmation) return (
    <div className="sc-step sc-confirm">
      <div className="sc-confirm-icon">📅</div>
      <h2>Appointment Booked!</h2>
      <p>Your appointment has been confirmed.</p>
      <div className="sc-confirm-id">
        Confirmation: <strong>{confirmation.confirmation_id}</strong>
      </div>
      <div className="sc-booking-details">
        <div className="sc-booking-row"><span>Provider</span><strong>{confirmation.provider_name}</strong></div>
        <div className="sc-booking-row"><span>Date</span><strong>{new Date(`${confirmation.slot_date}T${confirmation.slot_time}`).toLocaleDateString([], { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</strong></div>
        <div className="sc-booking-row"><span>Time</span><strong>{new Date(`${confirmation.slot_date}T${confirmation.slot_time}`).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</strong></div>
        <div className="sc-booking-row"><span>Location</span><strong>{confirmation.location}</strong></div>
      </div>
      {confirmation.instructions && (
        <div className="sc-booking-instructions">{confirmation.instructions}</div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 20 }}>
        <button className="sc-action-btn primary" onClick={downloadIcal}>
          📥 Add to Calendar (.ics)
        </button>
        <button className="sc-action-btn ghost" onClick={onDone}>Done</button>
      </div>
    </div>
  );

  const careLabels = { telehealth: "Telehealth", urgent_care: "Urgent Care", primary_care: "Primary Care" };

  return (
    <div className="sc-step">
      <div className="sc-step-header">
        <div className="sc-step-num">📅</div>
        <div>
          <h2>Book Your {careLabels[careType]} Appointment</h2>
          <p>Select an available slot — instant confirmation, no phone call needed.</p>
        </div>
      </div>

      {formStep && selectedSlot ? (
        <form onSubmit={handleBook}>
          <div className="sc-selected-slot-banner">
            <strong>{selectedSlot.provider_name}</strong> ·{" "}
            {new Date(`${selectedSlot.slot_date}T${selectedSlot.slot_time}`).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
            <button type="button" className="sc-change-slot" onClick={() => setFormStep(false)}>Change</button>
          </div>
          <div className="sc-field">
            <label>Your Name</label>
            <input type="text" className="sc-input" placeholder="Full name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} autoFocus />
          </div>
          <div className="sc-field">
            <label>Phone <span className="sc-optional">(for reminders)</span></label>
            <input type="tel" className="sc-input" placeholder="(555) 000-0000" value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} />
          </div>
          {error && <div className="sc-error">{error}</div>}
          <button type="submit" className="sc-btn-primary" disabled={booking != null}>
            {booking ? <><span className="sc-spinner" /> Booking…</> : "Confirm Appointment →"}
          </button>
        </form>
      ) : loading ? (
        <div style={{ textAlign: "center", padding: "40px 0" }}>
          <div className="sc-loading-spinner" style={{ margin: "0 auto 12px" }} />
          <div className="sc-loading-text">Finding available slots…</div>
        </div>
      ) : slots.length === 0 ? (
        <div className="sc-empty-slots">No slots available at this time. Please call the office directly.</div>
      ) : (
        <div className="sc-slots-list">
          {slots.map(slot => (
            <SlotCard key={slot.slot_id} slot={slot} onBook={handleSlotSelect} booking={booking} />
          ))}
        </div>
      )}

      <button className="sc-action-btn ghost" onClick={onSkip} style={{ marginTop: 12 }}>
        Skip — I'll call to schedule
      </button>
    </div>
  );
}

function StepResult({ result, demographicData, symptomsData, onPreRegister, onSchedule, onRestart }) {
  const level = result.care_level || "SELF_CARE";
  const meta = result.care_level_meta || CARE_LEVEL_CONFIG[level] || CARE_LEVEL_CONFIG.SELF_CARE;
  const cfg = CARE_LEVEL_CONFIG[level] || CARE_LEVEL_CONFIG.SELF_CARE;

  return (
    <div className="sc-step">
      <div className="sc-result-badge" style={{ background: cfg.bg, borderColor: cfg.border }}>
        <div className="sc-result-icon">{meta.icon || cfg.icon}</div>
        <div className="sc-result-text">
          <div className="sc-result-label" style={{ color: cfg.color }}>{meta.label || level}</div>
          <div className="sc-result-sub">{meta.sub || ""}</div>
        </div>
      </div>

      {result.headline && (
        <div className="sc-headline">{result.headline}</div>
      )}

      {result.reasoning && (
        <div className="sc-section">
          <h3>Clinical Reasoning</h3>
          <p>{result.reasoning}</p>
        </div>
      )}

      {result.red_flags?.length > 0 && (
        <div className="sc-section sc-red-flags">
          <h3>⚠️ Warning Signs — Seek Immediate Care If:</h3>
          <ul>
            {result.red_flags.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}

      {result.self_care_steps?.length > 0 && (
        <div className="sc-section">
          <h3>What You Can Do Now</h3>
          <ol className="sc-steps-list">
            {result.self_care_steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
        </div>
      )}

      {result.follow_up_timeframe && (
        <div className="sc-followup">
          <span>🕐</span>
          <span>Reassess if no improvement: <strong>{result.follow_up_timeframe}</strong></span>
        </div>
      )}

      {result.differential_dx?.length > 0 && (
        <div className="sc-section sc-diff-dx">
          <h3>Possible Causes</h3>
          <div className="sc-dx-chips">
            {result.differential_dx.map((d, i) => <span key={i} className="sc-dx-chip">{d}</span>)}
          </div>
        </div>
      )}

      {meta.action && (
        <div className="sc-action-note" style={{ borderColor: cfg.border }}>
          {meta.action}
        </div>
      )}

      <div className="sc-result-actions">
        <ActionButtons cta={cfg.cta} careLevel={level} onPreRegister={onPreRegister} onSchedule={onSchedule} />
        <button className="sc-action-btn ghost" onClick={onRestart}>
          ↩ Start Over
        </button>
      </div>

      <div className="sc-legal">
        This assessment is for informational purposes only and does not constitute medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider for medical concerns.
      </div>
    </div>
  );
}

function StepPreRegister({ demographicData, symptomsData, result, onDone }) {
  const [form, setForm] = useState({ name: "", phone: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [confirmation, setConfirmation] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { setError("Please enter your name"); return; }
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API_BASE}/check/pre-register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name.trim(),
          age: demographicData.age,
          sex: demographicData.sex,
          phone: form.phone.trim(),
          symptoms: symptomsData.symptoms,
          care_level: result.care_level,
          reasoning: result.reasoning || "",
          ed_ready_summary: result.ed_ready_summary || "",
        }),
      });
      if (!res.ok) throw new Error("Registration failed. Please try again.");
      const data = await res.json();
      setConfirmation(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (confirmation) {
    return (
      <div className="sc-step sc-confirm">
        <div className="sc-confirm-icon">✅</div>
        <h2>You're Registered</h2>
        <p>The ED team has been notified and is expecting you.</p>
        <div className="sc-confirm-id">
          Registration ID: <strong>{confirmation.patient_id}</strong>
        </div>
        <div className="sc-confirm-detail">
          Show this ID when you arrive. Head directly to the{" "}
          <strong>Emergency Department check-in desk</strong>.
        </div>
        <a
          href="https://maps.google.com/?q=emergency+room+near+me"
          target="_blank"
          rel="noopener noreferrer"
          className="sc-action-btn primary"
          style={{ display: "inline-block", marginTop: 16 }}
        >
          📍 Get Directions to ED
        </a>
        <button className="sc-action-btn ghost" onClick={onDone} style={{ marginTop: 8 }}>
          Done
        </button>
      </div>
    );
  }

  return (
    <div className="sc-step">
      <div className="sc-step-header">
        <div className="sc-step-num">5</div>
        <div>
          <h2>Pre-Register for the ED</h2>
          <p>Staff will be notified before you arrive, reducing your wait time.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="sc-field">
          <label>Full Name</label>
          <input
            type="text"
            className="sc-input"
            placeholder="Your legal name"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            autoFocus
          />
        </div>
        <div className="sc-field">
          <label>Phone Number <span className="sc-optional">(optional — for updates)</span></label>
          <input
            type="tel"
            className="sc-input"
            placeholder="(555) 000-0000"
            value={form.phone}
            onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
          />
        </div>
        {error && <div className="sc-error">{error}</div>}
        <button type="submit" className="sc-btn-primary" disabled={loading}>
          {loading ? <><span className="sc-spinner" /> Registering...</> : "Pre-Register Now →"}
        </button>
        <button type="button" className="sc-action-btn ghost" onClick={onDone} style={{ marginTop: 8 }}>
          Skip — I'll register at the desk
        </button>
      </form>
    </div>
  );
}

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ step, total }) {
  return (
    <div className="sc-progress-bar">
      <div className="sc-progress-fill" style={{ width: `${(step / total) * 100}%` }} />
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function SymptomCheck() {
  const [step, setStep] = useState(0); // 0=welcome, 1=demo, 2=symptoms, 3=qa, 4=result, 5=preregister, 6=schedule
  const [demographics, setDemographics] = useState({
    age: 0, sex: "", language: "English", riskFactors: [],
  });
  const [symptomsData, setSymptomsData] = useState({ symptoms: "" });
  const [qaData, setQaData] = useState({ questions: [], answers: {}, preliminary: "" });
  const [result, setResult] = useState(null);
  const [schedCareType, setSchedCareType] = useState("primary_care");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const changeDemographic = (key, val) => setDemographics(d => ({ ...d, [key]: val }));

  const callAssess = async (qaHistory = []) => {
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API_BASE}/check/assess`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          age: demographics.age,
          sex: demographics.sex,
          symptoms: symptomsData.symptoms,
          risk_factors: demographics.riskFactors,
          qa_history: qaHistory,
          language: demographics.language,
        }),
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || "Assessment failed");
      }
      const data = await res.json();

      if (data.status === "needs_info") {
        setQaData({ questions: data.questions || [], answers: {}, preliminary: data.preliminary_concern || "" });
        setStep(3);
      } else {
        setResult(data);
        setStep(4);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleQASubmit = async () => {
    const qaHistory = qaData.questions.map(q => ({
      question: q.text,
      answer: qaData.answers[q.id] || "",
    }));
    await callAssess(qaHistory);
  };

  const handleAnswer = (id, val) => {
    setQaData(d => ({ ...d, answers: { ...d.answers, [id]: val } }));
  };

  const handleSchedule = (careType) => {
    setSchedCareType(careType);
    setStep(6);
  };

  const restart = () => {
    setStep(0);
    setDemographics({ age: 0, sex: "", language: "English", riskFactors: [] });
    setSymptomsData({ symptoms: "" });
    setQaData({ questions: [], answers: {}, preliminary: "" });
    setResult(null);
    setError("");
  };

  const totalSteps = 4; // demo(1) symptoms(2) qa(3) result(4)

  return (
    <div className="sc-root">
      {/* Header */}
      <header className="sc-header">
        <div className="sc-header-inner">
          <div className="sc-logo">
            <span className="sc-logo-icon">⚕</span>
            <div>
              <div className="sc-logo-title">MediScan CareNavigator</div>
              <div className="sc-logo-sub">AI Symptom Assessment</div>
            </div>
          </div>
          {step > 0 && step < 5 && (
            <div className="sc-step-count">Step {step} of {totalSteps}</div>
          )}
        </div>
        {step > 0 && step < 5 && <ProgressBar step={step} total={totalSteps} />}
      </header>

      <main className="sc-main">
        <div className="sc-card">
          {/* Welcome */}
          {step === 0 && (
            <div className="sc-step sc-welcome">
              <div className="sc-welcome-hero">
                <div className="sc-welcome-icon">🩺</div>
                <h1>Should You Go to the ER?</h1>
                <p>
                  Get a clinical-grade recommendation in under 2 minutes —
                  powered by Claude AI with extended medical reasoning.
                </p>
              </div>

              <div className="sc-feature-grid">
                {[
                  ["🧠", "AI-Powered", "Advanced clinical reasoning using validated protocols (HEART, FAST, Wells)"],
                  ["⚡", "2 Minutes", "Quick, personalized assessment without waiting on hold"],
                  ["🏥", "Pre-Arrival", "Pre-register for the ED so staff are ready when you arrive"],
                  ["🌍", "10 Languages", "Available in English, Spanish, French, and 7 more"],
                ].map(([icon, title, desc]) => (
                  <div key={title} className="sc-feature-card">
                    <div className="sc-feature-icon">{icon}</div>
                    <div className="sc-feature-title">{title}</div>
                    <div className="sc-feature-desc">{desc}</div>
                  </div>
                ))}
              </div>

              <div className="sc-emergency-banner">
                <strong>🚨 Life-threatening emergency?</strong>
                {" "}Don't use this tool.{" "}
                <a href="tel:911" className="sc-911-link">Call 911 immediately.</a>
              </div>

              <button className="sc-btn-primary sc-btn-large" onClick={() => setStep(1)}>
                Check My Symptoms →
              </button>

              <div className="sc-legal">
                No account required. No personal data stored.
                This tool does not replace professional medical evaluation.
              </div>
            </div>
          )}

          {step === 1 && (
            <StepDemographics
              data={demographics}
              onChange={changeDemographic}
              onNext={() => setStep(2)}
            />
          )}

          {step === 2 && (
            <StepSymptoms
              data={symptomsData}
              onChange={(k, v) => setSymptomsData(d => ({ ...d, [k]: v }))}
              onNext={() => callAssess([])}
              loading={loading}
            />
          )}

          {/* Loading overlay between steps */}
          {loading && step === 2 && (
            <div className="sc-loading-overlay">
              <div className="sc-loading-spinner" />
              <div className="sc-loading-text">Analyzing your symptoms…</div>
              <div className="sc-loading-sub">Applying clinical decision rules</div>
            </div>
          )}

          {step === 3 && (
            <StepQA
              preliminary={qaData.preliminary}
              questions={qaData.questions}
              answers={qaData.answers}
              onAnswer={handleAnswer}
              onSubmit={handleQASubmit}
              loading={loading}
            />
          )}

          {step === 4 && result && (
            <StepResult
              result={result}
              demographicData={demographics}
              symptomsData={symptomsData}
              onPreRegister={() => setStep(5)}
              onSchedule={handleSchedule}
              onRestart={restart}
            />
          )}

          {step === 5 && (
            <StepPreRegister
              demographicData={demographics}
              symptomsData={symptomsData}
              result={result}
              onDone={() => setStep(4)}
            />
          )}

          {step === 6 && (
            <StepSchedule
              careType={schedCareType}
              demographicData={demographics}
              symptomsData={symptomsData}
              onDone={() => setStep(4)}
              onSkip={() => setStep(4)}
            />
          )}

          {error && (
            <div className="sc-error sc-error-main">
              <strong>Error:</strong> {error}
              <button onClick={() => setError("")} className="sc-error-close">✕</button>
            </div>
          )}
        </div>
      </main>

      <footer className="sc-footer">
        <p>MediScan CareNavigator · For informational purposes only · Not a substitute for professional medical advice</p>
        <p>
          <a href="/">← Back to MediScan Gateway</a>
          {" · "}
          <a href="/lobby">Lobby Display</a>
        </p>
      </footer>
    </div>
  );
}
