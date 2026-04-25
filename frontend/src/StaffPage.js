import { useState, useEffect, useCallback } from "react";
import { API_BASE } from "./AuthContext";

const ROLE_COLORS = { admin: "#7c3aed", nurse: "#0d9488", physician: "#0284c7" };
const ROLE_LABELS = { admin: "Admin", nurse: "Nurse", physician: "Physician" };

function RoleBadge({ role }) {
  const color = ROLE_COLORS[role] || "#64748b";
  return (
    <span style={{
      padding: "2px 10px", borderRadius: 20, fontSize: 11, fontWeight: 700,
      background: `${color}20`, color, border: `1px solid ${color}40`,
    }}>
      {ROLE_LABELS[role] || role}
    </span>
  );
}

function StatusDot({ active }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12 }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: active ? "#22c55e" : "#6b7280", display: "inline-block" }} />
      <span style={{ color: active ? "#22c55e" : "#6b7280" }}>{active ? "Active" : "Inactive"}</span>
    </span>
  );
}

function MFASetupModal({ user, authHeaders, onClose }) {
  const [qr, setQr] = useState(null);
  const [secret, setSecret] = useState("");
  const [backupCodes, setBackupCodes] = useState([]);
  const [code, setCode] = useState("");
  const [step, setStep] = useState("loading"); // loading | setup | verify | done
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/auth/mfa/setup`, { headers: authHeaders() })
      .then(r => r.json())
      .then(d => {
        setQr(d.qr_code_base64);
        setSecret(d.secret);
        setBackupCodes(d.backup_codes || []);
        setStep("setup");
      })
      .catch(() => setStep("error"));
  }, [authHeaders]);

  const handleVerify = async () => {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/auth/mfa/enable?code=${code}`, {
        method: "POST", headers: authHeaders(),
      });
      if (res.ok) { setStep("done"); }
      else { setError("Invalid code — try again."); }
    } catch { setError("Network error."); }
  };

  const modalStyle = {
    position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 2000,
    display: "flex", alignItems: "center", justifyContent: "center",
  };
  const boxStyle = {
    background: "#0f172a", border: "1px solid #1e293b", borderRadius: 16,
    padding: 32, width: 420, maxWidth: "90vw",
  };

  return (
    <div style={modalStyle} onClick={onClose}>
      <div style={boxStyle} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
          <h3 style={{ color: "#e2e8f0", margin: 0 }}>🔐 Set Up MFA</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#64748b", fontSize: 20, cursor: "pointer" }}>✕</button>
        </div>

        {step === "loading" && <p style={{ color: "#94a3b8" }}>Loading…</p>}

        {step === "setup" && (
          <>
            <p style={{ color: "#94a3b8", fontSize: 13, marginBottom: 16 }}>
              Scan this QR code with <strong style={{ color: "#e2e8f0" }}>Google Authenticator</strong>, Authy, or any TOTP app.
            </p>
            {qr && (
              <div style={{ textAlign: "center", marginBottom: 16 }}>
                <img src={`data:image/png;base64,${qr}`} alt="MFA QR Code" style={{ width: 180, height: 180, borderRadius: 8 }} />
              </div>
            )}
            <div style={{ background: "#1e293b", borderRadius: 8, padding: "8px 12px", marginBottom: 16, fontFamily: "monospace", fontSize: 12, color: "#94a3b8", wordBreak: "break-all" }}>
              Manual key: <span style={{ color: "#0d9488" }}>{secret}</span>
            </div>
            {backupCodes.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: "#64748b", marginBottom: 8, textTransform: "uppercase" }}>Backup codes — save these now</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4 }}>
                  {backupCodes.map(c => (
                    <span key={c} style={{ fontFamily: "monospace", fontSize: 12, color: "#cbd5e1", background: "#1e293b", padding: "3px 8px", borderRadius: 4 }}>{c}</span>
                  ))}
                </div>
              </div>
            )}
            <button onClick={() => setStep("verify")} style={{ width: "100%", padding: "10px 0", background: "#0d9488", color: "#fff", border: "none", borderRadius: 8, fontWeight: 700, cursor: "pointer" }}>
              I've scanned the code →
            </button>
          </>
        )}

        {step === "verify" && (
          <>
            <p style={{ color: "#94a3b8", fontSize: 13, marginBottom: 16 }}>Enter the 6-digit code from your authenticator app to confirm setup.</p>
            <input
              type="text" maxLength={6} placeholder="000000" autoFocus
              value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ""))}
              style={{ width: "100%", padding: "10px 14px", background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0", fontSize: 20, textAlign: "center", letterSpacing: 8, boxSizing: "border-box", marginBottom: 12 }}
            />
            {error && <p style={{ color: "#f87171", fontSize: 13, margin: "0 0 12px" }}>{error}</p>}
            <button onClick={handleVerify} disabled={code.length < 6}
              style={{ width: "100%", padding: "10px 0", background: "#0d9488", color: "#fff", border: "none", borderRadius: 8, fontWeight: 700, cursor: code.length < 6 ? "not-allowed" : "pointer", opacity: code.length < 6 ? 0.5 : 1 }}>
              Verify & Enable MFA
            </button>
          </>
        )}

        {step === "done" && (
          <>
            <div style={{ textAlign: "center", padding: "24px 0" }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
              <h3 style={{ color: "#4ade80", margin: "0 0 8px" }}>MFA Enabled</h3>
              <p style={{ color: "#94a3b8", fontSize: 14 }}>You'll be asked for a code on your next login.</p>
            </div>
            <button onClick={onClose} style={{ width: "100%", padding: "10px 0", background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 8, fontWeight: 700, cursor: "pointer" }}>
              Close
            </button>
          </>
        )}

        {step === "error" && <p style={{ color: "#f87171" }}>Failed to load MFA setup. Try again.</p>}
      </div>
    </div>
  );
}

function AddStaffModal({ authHeaders, onCreated, onClose }) {
  const [form, setForm] = useState({ username: "", password: "", role: "nurse", name: "", email: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.username || !form.password || !form.name) { setError("Username, name and password are required"); return; }
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API_BASE}/admin/users`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "Failed to create user"); return; }
      onCreated(data);
    } catch { setError("Network error"); }
    finally { setLoading(false); }
  };

  const modalStyle = {
    position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 2000,
    display: "flex", alignItems: "center", justifyContent: "center",
  };
  const boxStyle = {
    background: "#0f172a", border: "1px solid #1e293b", borderRadius: 16,
    padding: 32, width: 440, maxWidth: "90vw",
  };
  const inputStyle = {
    width: "100%", padding: "10px 14px", background: "#1e293b",
    border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0",
    fontSize: 14, boxSizing: "border-box", marginBottom: 12,
  };
  const labelStyle = { display: "block", fontSize: 12, color: "#64748b", marginBottom: 4 };

  return (
    <div style={modalStyle} onClick={onClose}>
      <div style={boxStyle} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
          <h3 style={{ color: "#e2e8f0", margin: 0 }}>Add Staff Member</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#64748b", fontSize: 20, cursor: "pointer" }}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          <label style={labelStyle}>Full Name</label>
          <input style={inputStyle} placeholder="Dr. Jane Smith" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />

          <label style={labelStyle}>Username</label>
          <input style={inputStyle} placeholder="jsmith" value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value.toLowerCase().replace(/\s/g, "") }))} />

          <label style={labelStyle}>Email (optional)</label>
          <input style={inputStyle} type="email" placeholder="jane@hospital.org" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />

          <label style={labelStyle}>Role</label>
          <select style={{ ...inputStyle, cursor: "pointer" }} value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
            <option value="nurse">Nurse</option>
            <option value="physician">Physician</option>
            <option value="admin">Admin</option>
          </select>

          <label style={labelStyle}>Temporary Password</label>
          <input style={inputStyle} type="password" placeholder="Min 8 characters" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />

          {error && <p style={{ color: "#f87171", fontSize: 13, margin: "0 0 12px" }}>{error}</p>}
          <button type="submit" disabled={loading} style={{ width: "100%", padding: "10px 0", background: "#0d9488", color: "#fff", border: "none", borderRadius: 8, fontWeight: 700, cursor: "pointer" }}>
            {loading ? "Creating…" : "Create Account →"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function StaffPage({ user }) {
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [showMFA, setShowMFA] = useState(false);
  const [resetTarget, setResetTarget] = useState(null);
  const [resetPw, setResetPw] = useState("");
  const [resetLoading, setResetLoading] = useState(false);
  const [resetMsg, setResetMsg] = useState("");

  const authHeaders = useCallback(() => ({
    Authorization: `Bearer ${user?.token}`,
    "Content-Type": "application/json",
  }), [user?.token]);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/users`, { headers: authHeaders() });
      setStaff(await res.json());
    } catch { }
    finally { setLoading(false); }
  }, [authHeaders]);

  useEffect(() => { load(); }, [load]);

  const toggleActive = async (username, currentActive) => {
    await fetch(`${API_BASE}/admin/users/${username}`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({ active: !currentActive }),
    });
    load();
  };

  const disableMFA = async (username) => {
    await fetch(`${API_BASE}/auth/mfa/disable?username=${username}`, {
      method: "POST", headers: authHeaders(),
    });
    load();
  };

  const handleReset = async (e) => {
    e.preventDefault();
    if (!resetPw || resetPw.length < 8) return;
    setResetLoading(true); setResetMsg("");
    try {
      const res = await fetch(`${API_BASE}/admin/users/${resetTarget}/reset-password?new_password=${encodeURIComponent(resetPw)}`, {
        method: "POST", headers: authHeaders(),
      });
      if (res.ok) { setResetMsg("Password reset successfully."); setResetPw(""); }
      else { const d = await res.json(); setResetMsg(d.detail || "Failed"); }
    } catch { setResetMsg("Network error"); }
    finally { setResetLoading(false); }
  };

  const row = {
    display: "flex", alignItems: "center", gap: 16,
    padding: "14px 20px", background: "#080f1a",
    border: "1px solid #1e293b", borderRadius: 10, marginBottom: 8,
  };
  const actionBtn = {
    padding: "4px 12px", borderRadius: 6, fontSize: 12, fontWeight: 600,
    cursor: "pointer", border: "1px solid #334155", background: "transparent", color: "#94a3b8",
  };

  return (
    <div style={{ padding: "28px 32px", maxWidth: 900, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h2 style={{ color: "#e2e8f0", margin: "0 0 4px" }}>Staff Management</h2>
          <p style={{ color: "#64748b", margin: 0, fontSize: 14 }}>Create accounts, manage roles, and enforce MFA.</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={() => setShowMFA(true)}
            style={{ padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", background: "#1e293b", color: "#0d9488", border: "1px solid #0d948840" }}
          >
            🔐 My MFA Setup
          </button>
          <button
            onClick={() => setShowAdd(true)}
            style={{ padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: "pointer", background: "#0d9488", color: "#fff", border: "none" }}
          >
            + Add Staff
          </button>
        </div>
      </div>

      {/* Password reset panel */}
      {resetTarget && (
        <div style={{ background: "#080f1a", border: "1px solid #334155", borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <div style={{ color: "#e2e8f0", fontWeight: 600, marginBottom: 12 }}>Reset password for <span style={{ color: "#0d9488" }}>{resetTarget}</span></div>
          <form onSubmit={handleReset} style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <input
              type="password" placeholder="New password (min 8 chars)" value={resetPw}
              onChange={e => setResetPw(e.target.value)}
              style={{ flex: 1, padding: "8px 12px", background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0", fontSize: 13 }}
            />
            <button type="submit" disabled={resetLoading || resetPw.length < 8}
              style={{ padding: "8px 16px", background: "#0d9488", color: "#fff", border: "none", borderRadius: 8, fontWeight: 700, cursor: "pointer" }}>
              {resetLoading ? "Saving…" : "Reset"}
            </button>
            <button type="button" onClick={() => { setResetTarget(null); setResetMsg(""); }}
              style={{ padding: "8px 12px", background: "transparent", color: "#64748b", border: "1px solid #334155", borderRadius: 8, cursor: "pointer" }}>
              Cancel
            </button>
          </form>
          {resetMsg && <p style={{ color: "#4ade80", fontSize: 13, margin: "8px 0 0" }}>{resetMsg}</p>}
        </div>
      )}

      {loading ? (
        <p style={{ color: "#64748b" }}>Loading…</p>
      ) : (
        staff.map(s => (
          <div key={s.username} style={{ ...row, opacity: s.active ? 1 : 0.5 }}>
            <div style={{ width: 40, height: 40, borderRadius: "50%", background: `${ROLE_COLORS[s.role] || "#334155"}20`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>
              {s.role === "admin" ? "🛡" : s.role === "physician" ? "🩺" : "💉"}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ color: "#e2e8f0", fontWeight: 600, fontSize: 14 }}>{s.name}</span>
                <RoleBadge role={s.role} />
                <StatusDot active={s.active} />
                {s.mfa_enabled && (
                  <span style={{ fontSize: 11, color: "#4ade80", background: "#052e16", border: "1px solid #16a34a", borderRadius: 20, padding: "1px 8px" }}>🔐 MFA ON</span>
                )}
              </div>
              <div style={{ fontSize: 12, color: "#475569", marginTop: 2 }}>
                @{s.username}
                {s.email ? ` · ${s.email}` : ""}
                {s.last_login ? ` · Last login: ${new Date(s.last_login).toLocaleDateString()}` : ""}
                {s.created_by === "system" ? " · System account" : ""}
              </div>
            </div>
            <div style={{ display: "flex", gap: 6, flexShrink: 0, flexWrap: "wrap" }}>
              {s.created_by !== "system" && (
                <>
                  <button style={actionBtn} onClick={() => { setResetTarget(s.username); setResetMsg(""); }}>
                    🔑 Reset PW
                  </button>
                  <button
                    style={{ ...actionBtn, color: s.active ? "#f87171" : "#4ade80", borderColor: s.active ? "#7f1d1d" : "#14532d" }}
                    onClick={() => toggleActive(s.username, s.active)}
                  >
                    {s.active ? "Deactivate" : "Reactivate"}
                  </button>
                </>
              )}
              {s.mfa_enabled && s.created_by !== "system" && (
                <button style={{ ...actionBtn, color: "#f97316", borderColor: "#7c2d12" }} onClick={() => disableMFA(s.username)}>
                  Disable MFA
                </button>
              )}
            </div>
          </div>
        ))
      )}

      {staff.length === 0 && !loading && (
        <div style={{ textAlign: "center", padding: "40px 0", color: "#475569" }}>No staff found.</div>
      )}

      {showAdd && (
        <AddStaffModal
          authHeaders={authHeaders}
          onCreated={() => { setShowAdd(false); load(); }}
          onClose={() => setShowAdd(false)}
        />
      )}

      {showMFA && (
        <MFASetupModal
          user={user}
          authHeaders={authHeaders}
          onClose={() => { setShowMFA(false); load(); }}
        />
      )}
    </div>
  );
}
