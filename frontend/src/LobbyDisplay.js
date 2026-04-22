/**
 * Public lobby TV display — no PHI, no login required.
 * Access at: your-app.vercel.app/lobby
 * Designed for 16:9 displays mounted in ED waiting areas.
 */
import { useState, useEffect, useCallback } from "react";
import { useWebSocket } from "./hooks/useWebSocket";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";
const WS_BASE  = API_BASE.replace(/^https/, "wss").replace(/^http/, "ws");

const ESI_CONFIG = {
  1: { color: "#dc2626", bg: "#1a0505", label: "CRITICAL",    icon: "■" },
  2: { color: "#ea580c", bg: "#1a0a05", label: "HIGH ACUITY", icon: "■" },
  3: { color: "#d97706", bg: "#1a1205", label: "URGENT",      icon: "■" },
  4: { color: "#16a34a", bg: "#051a0a", label: "LESS URGENT", icon: "■" },
  5: { color: "#6b7280", bg: "#111827", label: "NON-URGENT",  icon: "■" },
};

function Clock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div style={{ textAlign: "right" }}>
      <div style={{ fontSize: 42, fontWeight: 200, color: "#e2e8f0", letterSpacing: -1 }}>
        {time.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
      </div>
      <div style={{ fontSize: 14, color: "#475569", marginTop: -4 }}>
        {time.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
      </div>
    </div>
  );
}

function ESIBar({ esi, count, waitMin }) {
  const cfg = ESI_CONFIG[esi];
  if (count === 0) return null;
  return (
    <div style={{
      background: cfg.bg,
      border: `1px solid ${cfg.color}22`,
      borderLeft: `4px solid ${cfg.color}`,
      borderRadius: 10,
      padding: "18px 24px",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ color: cfg.color, fontSize: 28, fontWeight: 900 }}>{count}</span>
        <div>
          <div style={{ color: cfg.color, fontWeight: 700, fontSize: 15 }}>ESI {esi} — {cfg.label}</div>
          {waitMin !== null && (
            <div style={{ color: "#64748b", fontSize: 13, marginTop: 2 }}>
              Est. wait: {waitMin > 0 ? `~${waitMin} min` : "Immediate"}
            </div>
          )}
        </div>
      </div>
      <div style={{ fontSize: 13, color: "#334155" }}>
        {count === 1 ? "1 patient" : `${count} patients`}
      </div>
    </div>
  );
}

function Ticker({ events }) {
  if (!events.length) return null;
  return (
    <div style={{
      background: "#0d1526",
      borderTop: "1px solid #1e293b",
      padding: "10px 32px",
      overflow: "hidden",
      whiteSpace: "nowrap",
    }}>
      <span style={{ color: "#334155", fontSize: 13, marginRight: 24, fontWeight: 600 }}>LIVE</span>
      <span style={{ color: "#475569", fontSize: 13 }}>
        {events.slice(-6).join("  ·  ")}
      </span>
    </div>
  );
}

export default function LobbyDisplay() {
  const [stats, setStats] = useState({
    queue: { total_patients: 0, esi_breakdown: {}, avg_wait_minutes: 0 },
    capacity: { occupancy_percent: 0, available_beds: 0 },
    alerts: [],
  });
  const [ticker, setTicker] = useState([]);
  const [wsOk, setWsOk] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/analytics`, {
        headers: { Authorization: "Bearer lobby-public" },
      }).catch(() => null);
      // analytics requires auth — we'll just use WS data + a public endpoint if added
    } catch (_) {}
  }, []);

  const handleWsMsg = useCallback((msg) => {
    setWsOk(true);
    if (msg.event === "patient_added") {
      setTicker(prev => [
        ...prev,
        `Patient checked in — Room ${msg.room_assignment || "assigned"} · ESI ${msg.esi_level}`,
      ]);
      setStats(prev => {
        const esi = msg.esi_level;
        const breakdown = { ...prev.queue.esi_breakdown };
        breakdown[String(esi)] = (breakdown[String(esi)] || 0) + 1;
        return {
          ...prev,
          queue: {
            ...prev.queue,
            total_patients: prev.queue.total_patients + 1,
            esi_breakdown: breakdown,
          },
        };
      });
    } else if (msg.event === "patient_discharged") {
      setTicker(prev => [...prev, "Patient discharged — bed now available"]);
      setStats(prev => ({
        ...prev,
        queue: { ...prev.queue, total_patients: Math.max(0, prev.queue.total_patients - 1) },
      }));
    } else if (msg.event === "bed_updated") {
      if (msg.status === "available") {
        setTicker(prev => [...prev, `${msg.room} is now available`]);
      }
    } else if (msg.event === "monitor_alert") {
      const a = msg.alert || {};
      if (a.level === "critical") {
        setTicker(prev => [...prev, a.message || "Clinical alert triggered"]);
      }
    }
  }, []);

  const { connected } = useWebSocket(`${WS_BASE}/ws/lobby`, handleWsMsg);

  // Poll a public summary endpoint (if exists) as fallback
  useEffect(() => {
    const t = setInterval(fetchStats, 30000);
    return () => clearInterval(t);
  }, [fetchStats]);

  const q = stats.queue;
  const hasPatients = q.total_patients > 0;

  return (
    <div style={{
      background: "#060b14",
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      fontFamily: "'Inter', -apple-system, sans-serif",
    }}>
      {/* Header */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "24px 40px",
        borderBottom: "1px solid #0d1526",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 36, lineHeight: 1 }}>⚕</span>
          <div>
            <div style={{ fontSize: 22, fontWeight: 700, color: "#e2e8f0" }}>MediScan Gateway</div>
            <div style={{ fontSize: 13, color: "#475569" }}>Emergency Department — Patient Status Board</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 8, height: 8, borderRadius: "50%",
              background: connected ? "#22c55e" : "#f59e0b",
              boxShadow: connected ? "0 0 6px #22c55e" : "none",
            }} />
            <span style={{ fontSize: 12, color: "#475569" }}>{connected ? "Live" : "Connecting…"}</span>
          </div>
          <Clock />
        </div>
      </div>

      {/* Main area */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 320px", gap: 0 }}>
        {/* Left — ESI queue */}
        <div style={{ padding: "32px 40px", borderRight: "1px solid #0d1526" }}>
          <div style={{ fontSize: 13, color: "#334155", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 20 }}>
            Current Queue
          </div>

          {!hasPatients ? (
            <div style={{ textAlign: "center", padding: "60px 0" }}>
              <div style={{ fontSize: 48, opacity: 0.2 }}>🏥</div>
              <div style={{ color: "#1e293b", fontSize: 18, marginTop: 16 }}>No patients currently in queue</div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[1, 2, 3, 4, 5].map(esi => (
                <ESIBar
                  key={esi}
                  esi={esi}
                  count={q.esi_breakdown?.[String(esi)] || 0}
                  waitMin={esi <= 2 ? 0 : esi === 3 ? q.avg_wait_minutes : null}
                />
              ))}
            </div>
          )}
        </div>

        {/* Right — info panel */}
        <div style={{ padding: "32px 28px", display: "flex", flexDirection: "column", gap: 24 }}>
          {/* Total */}
          <div style={{ textAlign: "center", padding: "24px", background: "#0d1526", borderRadius: 12 }}>
            <div style={{ fontSize: 64, fontWeight: 200, color: "#e2e8f0", lineHeight: 1 }}>{q.total_patients}</div>
            <div style={{ fontSize: 14, color: "#334155", marginTop: 6 }}>patients in queue</div>
          </div>

          {/* Avg wait */}
          {q.avg_wait_minutes > 0 && (
            <div style={{ textAlign: "center", padding: "20px", background: "#0d1526", borderRadius: 12 }}>
              <div style={{ fontSize: 40, fontWeight: 200, color: "#d97706", lineHeight: 1 }}>~{q.avg_wait_minutes}</div>
              <div style={{ fontSize: 13, color: "#334155", marginTop: 4 }}>avg wait (min)</div>
            </div>
          )}

          {/* Info messages */}
          <div style={{ fontSize: 13, color: "#1e293b", lineHeight: 1.8 }}>
            <div>✓ Automatic vitals scanning at entry</div>
            <div>✓ AI triage in under 15 seconds</div>
            <div>✓ SMS updates sent to your phone</div>
            <div>✓ Family notification for ESI 1–3</div>
          </div>

          {/* Legal */}
          <div style={{ marginTop: "auto", fontSize: 11, color: "#1e293b", lineHeight: 1.6 }}>
            For medical emergencies, alert staff immediately.
            If your condition worsens while waiting, please
            notify the triage desk at once.
          </div>
        </div>
      </div>

      {/* Ticker */}
      <Ticker events={ticker} />
    </div>
  );
}
