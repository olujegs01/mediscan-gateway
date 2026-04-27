import { useState, useEffect, useCallback } from "react";
import { API_BASE } from "./AuthContext";

const ESI_COLORS = { 1: "#dc2626", 2: "#ea580c", 3: "#ca8a04", 4: "#16a34a", 5: "#6b7280" };
const ESI_LABELS = { 1: "Critical", 2: "High", 3: "Urgent", 4: "Less Urgent", 5: "Non-Urgent" };

function BigStat({ label, value, color = "#0d9488", sub, pulse }) {
  return (
    <div style={{
      background: "#060e1a", borderRadius: 16, padding: "28px 24px", flex: 1,
      border: `1px solid ${color}30`, position: "relative", overflow: "hidden",
    }}>
      {pulse && (
        <div style={{
          position: "absolute", top: 12, right: 12, width: 10, height: 10,
          borderRadius: "50%", background: color, animation: "ping 1s infinite",
        }} />
      )}
      <div style={{ fontSize: 48, fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 14, color: "#94a3b8", marginTop: 6 }}>{label}</div>
      {sub && <div style={{ fontSize: 12, color: "#475569", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function WaitBar({ name, esi, waitMin, room, escalated }) {
  const color = ESI_COLORS[esi] || "#6b7280";
  const maxWait = esi <= 2 ? 30 : esi === 3 ? 120 : 240;
  const pct = Math.min(100, (waitMin / maxWait) * 100);
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 16, padding: "10px 0",
      borderBottom: "1px solid #1e293b",
      background: escalated ? "rgba(220,38,38,0.05)" : "transparent",
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: "50%", background: color + "20",
        border: `2px solid ${color}`, display: "flex", alignItems: "center",
        justifyContent: "center", fontSize: 11, fontWeight: 700, color, flexShrink: 0,
      }}>{esi}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ fontSize: 14, color: "#e2e8f0", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {escalated && <span style={{ color: "#dc2626", marginRight: 6 }}>⚠</span>}
            {name}
          </span>
          <span style={{ fontSize: 13, color: waitMin > (esi <= 2 ? 5 : 60) ? "#dc2626" : "#94a3b8", flexShrink: 0, marginLeft: 8 }}>
            {waitMin} min
          </span>
        </div>
        <div style={{ height: 4, borderRadius: 2, background: "#1e293b", overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`, background: escalated ? "#dc2626" : color, borderRadius: 2, transition: "width 1s" }} />
        </div>
      </div>
      <div style={{ fontSize: 11, color: "#475569", flexShrink: 0, width: 70, textAlign: "right" }}>{room}</div>
    </div>
  );
}

export default function ChargeDashboard({ user }) {
  const [data, setData] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/charge/dashboard`, {
        headers: { Authorization: `Bearer ${user?.token}` },
      });
      if (r.ok) setData(await r.json());
    } catch {}
  }, [user?.token]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Live clock
  const [clock, setClock] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  if (!data) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "60vh", color: "#475569", fontSize: 18 }}>
        Loading charge dashboard…
      </div>
    );
  }

  const { queue_depth, escalated_count, sepsis_active, bed_summary, queue_by_esi, longest_waits, throughput_8h } = data;

  return (
    <div style={{ padding: "24px 32px", minHeight: "100vh", background: "#030711" }}>
      <style>{`@keyframes ping { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.6; transform: scale(1.4); } }`}</style>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
        <div>
          <div style={{ fontSize: 28, fontWeight: 800, color: "#e2e8f0" }}>⚕ Charge Nurse Dashboard</div>
          <div style={{ fontSize: 14, color: "#475569", marginTop: 4 }}>Auto-refreshes every 15 seconds</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 36, fontWeight: 700, color: "#0d9488", fontVariantNumeric: "tabular-nums" }}>
            {clock.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </div>
          <div style={{ fontSize: 13, color: "#475569" }}>
            {clock.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
          </div>
        </div>
      </div>

      {/* Escalation alert banner */}
      {escalated_count > 0 && (
        <div style={{
          background: "rgba(220,38,38,0.15)", border: "1px solid #dc2626", borderRadius: 12,
          padding: "16px 24px", marginBottom: 24, display: "flex", alignItems: "center", gap: 16,
        }}>
          <span style={{ fontSize: 28 }}>🚨</span>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#f87171" }}>
              {escalated_count} patient{escalated_count > 1 ? "s" : ""} with wait time violation
            </div>
            <div style={{ fontSize: 13, color: "#94a3b8" }}>
              ESI 1–2 patients waiting &gt;5 min · ESI 3 patients waiting &gt;60 min
            </div>
          </div>
        </div>
      )}

      {/* Top KPIs */}
      <div style={{ display: "flex", gap: 16, marginBottom: 32 }}>
        <BigStat label="Patients in Queue" value={queue_depth} color="#0d9488" sub="Active" />
        <BigStat label="Wait Escalations" value={escalated_count} color={escalated_count > 0 ? "#dc2626" : "#16a34a"} pulse={escalated_count > 0} />
        <BigStat label="Beds Available" value={bed_summary.available_beds} color="#16a34a" sub={`${bed_summary.occupancy_percent}% occupied`} />
        <BigStat label="Boarding" value={bed_summary.boarding_patients} color={bed_summary.boarding_patients > 3 ? "#dc2626" : "#ea580c"} />
        <BigStat label="Discharged (8h)" value={throughput_8h} color="#0284c7" sub="Throughput" />
        {sepsis_active > 0 && <BigStat label="Sepsis Active" value={sepsis_active} color="#dc2626" pulse />}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginBottom: 24 }}>
        {/* Queue by ESI */}
        <div style={{ background: "#060e1a", borderRadius: 16, padding: 24, border: "1px solid #1e293b" }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#e2e8f0", marginBottom: 20 }}>Queue by Priority</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {[1, 2, 3, 4, 5].map(esi => {
              const pts = queue_by_esi[String(esi)] || [];
              const color = ESI_COLORS[esi];
              const hasEscalated = pts.some(p => p.escalated);
              return (
                <div key={esi} style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: 8, background: color + "20",
                    border: `2px solid ${color}`, display: "flex", alignItems: "center",
                    justifyContent: "center", fontWeight: 800, color, fontSize: 14, flexShrink: 0,
                  }}>ESI{esi}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 13, color: "#94a3b8" }}>{ESI_LABELS[esi]}</span>
                      <span style={{ fontSize: 16, fontWeight: 700, color: hasEscalated ? "#dc2626" : "#e2e8f0" }}>
                        {pts.length}
                        {hasEscalated && <span style={{ fontSize: 11, marginLeft: 6, color: "#dc2626" }}>⚠ escalated</span>}
                      </span>
                    </div>
                    <div style={{ height: 6, borderRadius: 3, background: "#1e293b", overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${Math.min(100, pts.length * 10)}%`, background: color, borderRadius: 3 }} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Longest waits */}
        <div style={{ background: "#060e1a", borderRadius: 16, padding: 24, border: "1px solid #1e293b" }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#e2e8f0", marginBottom: 16 }}>Longest Waiting</div>
          {longest_waits.length === 0 ? (
            <div style={{ color: "#475569", fontSize: 14, paddingTop: 16 }}>No patients in queue</div>
          ) : (
            longest_waits.map((p, i) => (
              <WaitBar key={i} name={p.name} esi={p.esi} waitMin={p.wait_min} room={p.room} escalated={p.escalated} />
            ))
          )}
        </div>
      </div>

      {/* Bed summary bar */}
      <div style={{ background: "#060e1a", borderRadius: 16, padding: 24, border: "1px solid #1e293b" }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#e2e8f0", marginBottom: 16 }}>Bed Capacity</div>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
          {[
            { label: "Available", val: bed_summary.available_beds, color: "#16a34a" },
            { label: "Occupied", val: bed_summary.occupied_beds, color: "#ea580c" },
            { label: "Boarding", val: bed_summary.boarding_patients, color: "#dc2626" },
            { label: "Cleaning", val: bed_summary.cleaning_beds, color: "#94a3b8" },
            { label: "Total", val: bed_summary.total_beds, color: "#475569" },
          ].map(({ label, val, color }) => (
            <div key={label} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 36, fontWeight: 800, color }}>{val}</div>
              <div style={{ fontSize: 12, color: "#475569" }}>{label}</div>
            </div>
          ))}
          <div style={{ flex: 1, display: "flex", alignItems: "center" }}>
            <div style={{ width: "100%", height: 20, borderRadius: 10, background: "#1e293b", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${bed_summary.occupancy_percent}%`, background: bed_summary.occupancy_percent >= 90 ? "#dc2626" : bed_summary.occupancy_percent >= 75 ? "#ea580c" : "#0d9488", borderRadius: 10, transition: "width 1s" }} />
            </div>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0", marginLeft: 12, flexShrink: 0 }}>
              {bed_summary.occupancy_percent}%
            </span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div style={{ textAlign: "center", marginTop: 24, fontSize: 12, color: "#1e293b" }}>
        MediScan Gateway · Charge Nurse View · Last updated {new Date().toLocaleTimeString()}
      </div>
    </div>
  );
}
