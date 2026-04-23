import { useState, useEffect, useCallback } from "react";
import { API_BASE } from "./AuthContext";

const TIER_CONFIG = {
  starter: {
    name: "Starter",
    price: "$4,500/mo",
    color: "#0284c7",
    features: ["Walk-Through Triage Scanner", "AI CareNavigator (500/mo)", "Live ER Queue & Bed Board", "HIPAA Audit Log"],
  },
  growth: {
    name: "Growth",
    price: "$12,000/mo",
    color: "#0d9488",
    features: ["Everything in Starter", "Clinical Journeys™", "AI SOAP Notes", "Outcomes Command Dashboard", "BAA + Compliance Center"],
  },
  enterprise: {
    name: "Enterprise",
    price: "Custom",
    color: "#7c3aed",
    features: ["Everything in Growth", "Epic / EHR deep integration", "White-label branding", "Dedicated CSM + SLA"],
  },
};

function UpgradeCard({ tier, onCheckout, loading }) {
  const cfg = TIER_CONFIG[tier] || TIER_CONFIG.starter;
  return (
    <div style={{
      background: "#080f1a", border: `1px solid ${cfg.color}40`, borderRadius: 16,
      padding: 28, flex: 1, minWidth: 220,
    }}>
      <div style={{ color: cfg.color, fontWeight: 700, fontSize: 18, marginBottom: 6 }}>{cfg.name}</div>
      <div style={{ color: "#e2e8f0", fontSize: 24, fontWeight: 700, marginBottom: 16 }}>{cfg.price}</div>
      <ul style={{ listStyle: "none", padding: 0, margin: "0 0 20px", fontSize: 13, color: "#94a3b8" }}>
        {cfg.features.map(f => (
          <li key={f} style={{ marginBottom: 6 }}>
            <span style={{ color: cfg.color, marginRight: 6 }}>✓</span>{f}
          </li>
        ))}
      </ul>
      {tier !== "enterprise" ? (
        <button
          onClick={() => onCheckout(tier)}
          disabled={loading === tier}
          style={{
            width: "100%", padding: "10px 0", borderRadius: 8, fontWeight: 700,
            fontSize: 14, cursor: loading === tier ? "not-allowed" : "pointer",
            background: cfg.color, color: "#fff", border: "none",
          }}
        >
          {loading === tier ? "Redirecting…" : "Subscribe →"}
        </button>
      ) : (
        <a
          href="mailto:sales@mediscan.health"
          style={{
            display: "block", textAlign: "center", padding: "10px 0", borderRadius: 8,
            fontWeight: 700, fontSize: 14, background: "transparent",
            border: `1px solid ${cfg.color}`, color: cfg.color, textDecoration: "none",
          }}
        >
          Contact Sales →
        </a>
      )}
    </div>
  );
}

export default function BillingPage({ user }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(null);
  const [error, setError] = useState("");
  const [demoMsg, setDemoMsg] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/billing/status`);
      setStatus(await res.json());
    } catch {
      setStatus({ stripe_configured: false, subscription: null });
    }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const handleCheckout = async (tier) => {
    setLoading(tier);
    setError("");
    setDemoMsg("");
    try {
      const res = await fetch(`${API_BASE}/billing/create-checkout-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier, email: user?.username ? undefined : undefined }),
      });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else if (data.demo_mode) {
        setDemoMsg(data.message);
      } else if (data.error) {
        setError(data.error);
      }
    } catch (e) {
      setError("Network error — please try again.");
    } finally {
      setLoading(null);
    }
  };

  const sub = status?.subscription;
  const stripeOk = status?.stripe_configured;

  return (
    <div style={{ padding: "28px 32px", maxWidth: 900, margin: "0 auto" }}>
      <h2 style={{ color: "#e2e8f0", margin: "0 0 4px" }}>Billing & Subscription</h2>
      <p style={{ color: "#64748b", marginTop: 0, marginBottom: 28, fontSize: 14 }}>
        Manage your MediScan Gateway subscription plan.
      </p>

      {/* Current subscription */}
      {sub ? (
        <div style={{
          background: "#080f1a", border: `1px solid ${TIER_CONFIG[sub.tier]?.color || "#0d9488"}50`,
          borderRadius: 16, padding: 28, marginBottom: 28,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: 12, color: "#64748b", textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 6 }}>
                Current Plan
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: TIER_CONFIG[sub.tier]?.color || "#0d9488" }}>
                {TIER_CONFIG[sub.tier]?.name || sub.tier}
              </div>
              <div style={{ color: "#94a3b8", fontSize: 14, marginTop: 4 }}>
                {TIER_CONFIG[sub.tier]?.price || "Custom"}
              </div>
            </div>
            <div style={{
              padding: "6px 14px", borderRadius: 20, fontSize: 12, fontWeight: 600,
              background: sub.status === "active" ? "#052e16" : "#450a0a",
              color: sub.status === "active" ? "#4ade80" : "#f87171",
              border: `1px solid ${sub.status === "active" ? "#16a34a" : "#dc2626"}`,
            }}>
              {sub.status?.toUpperCase()}
            </div>
          </div>
          <div style={{ marginTop: 20, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
            {[
              ["Customer", sub.customer_email || "—"],
              ["Hospital", sub.hospital_name || "—"],
              ["Since", sub.created_at ? new Date(sub.created_at).toLocaleDateString() : "—"],
            ].map(([label, val]) => (
              <div key={label}>
                <div style={{ fontSize: 11, color: "#475569", marginBottom: 3 }}>{label}</div>
                <div style={{ fontSize: 14, color: "#cbd5e1" }}>{val}</div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div style={{
          background: "#080f1a", border: "1px solid #1e293b", borderRadius: 16,
          padding: 24, marginBottom: 28, textAlign: "center",
        }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>📋</div>
          <div style={{ color: "#94a3b8", fontSize: 15, marginBottom: 4 }}>No active subscription</div>
          <div style={{ color: "#475569", fontSize: 13 }}>
            Choose a plan below to unlock all MediScan Gateway features.
          </div>
        </div>
      )}

      {/* Stripe status notice */}
      {!stripeOk && (
        <div style={{
          padding: "12px 16px", background: "rgba(202,138,4,0.1)", border: "1px solid rgba(202,138,4,0.3)",
          borderRadius: 10, marginBottom: 20, fontSize: 13, color: "#fbbf24",
        }}>
          ⚠ Stripe is not configured in this environment. Set <code>STRIPE_SECRET_KEY</code> to enable live checkout.
          Contact <a href="mailto:sales@mediscan.health" style={{ color: "#fbbf24" }}>sales@mediscan.health</a> to subscribe.
        </div>
      )}

      {demoMsg && (
        <div style={{
          padding: "12px 16px", background: "rgba(13,148,136,0.1)", border: "1px solid rgba(13,148,136,0.3)",
          borderRadius: 10, marginBottom: 20, fontSize: 13, color: "#5eead4",
        }}>
          ℹ {demoMsg}
        </div>
      )}

      {error && (
        <div style={{
          padding: "12px 16px", background: "rgba(220,38,38,0.1)", border: "1px solid rgba(220,38,38,0.3)",
          borderRadius: 10, marginBottom: 20, fontSize: 13, color: "#f87171",
        }}>
          {error}
        </div>
      )}

      {/* Plan cards */}
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        {["starter", "growth", "enterprise"].map(tier => (
          <UpgradeCard key={tier} tier={tier} onCheckout={handleCheckout} loading={loading} />
        ))}
      </div>

      {/* FAQ */}
      <div style={{ marginTop: 40 }}>
        <h3 style={{ color: "#94a3b8", fontSize: 13, textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 16 }}>
          Billing FAQ
        </h3>
        {[
          ["Can I cancel anytime?", "Yes. Cancel from Stripe Customer Portal or email billing@mediscan.health — no penalties."],
          ["What payment methods are accepted?", "All major credit cards via Stripe. ACH/wire available for Enterprise plans."],
          ["Is there a free trial?", "Growth plan includes a 14-day free trial. No credit card required to start."],
          ["Do you offer annual pricing?", "Yes — annual contracts receive a 15% discount. Contact sales for details."],
        ].map(([q, a]) => (
          <div key={q} style={{
            marginBottom: 16, padding: "16px 20px", background: "#080f1a",
            border: "1px solid #1e293b", borderRadius: 10,
          }}>
            <div style={{ fontWeight: 600, fontSize: 14, color: "#e2e8f0", marginBottom: 6 }}>{q}</div>
            <div style={{ fontSize: 13, color: "#64748b" }}>{a}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
