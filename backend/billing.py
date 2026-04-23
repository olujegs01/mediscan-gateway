"""
Stripe billing — creates Checkout sessions for Starter/Growth plans.
Set STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET to go live.
Without keys, returns demo_mode=True so the UI degrades gracefully.
"""
import os

STRIPE_SECRET_KEY     = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_STARTER  = os.getenv("STRIPE_PRICE_STARTER", "")
STRIPE_PRICE_GROWTH   = os.getenv("STRIPE_PRICE_GROWTH", "")
_FRONTEND_URL         = os.getenv("FRONTEND_URL", "https://mediscan-gateway.vercel.app")


def stripe_available() -> bool:
    return bool(STRIPE_SECRET_KEY)


def create_checkout_session(tier: str, email: str = None, hospital: str = None) -> dict:
    if not stripe_available():
        return {
            "demo_mode": True,
            "message": "Stripe not configured. Contact sales@mediscan.health to subscribe.",
            "checkout_url": None,
        }

    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    price_id = STRIPE_PRICE_STARTER if tier == "starter" else STRIPE_PRICE_GROWTH
    if not price_id:
        return {
            "demo_mode": True,
            "message": f"Price ID for '{tier}' plan not set. Set STRIPE_PRICE_{tier.upper()} env var.",
            "checkout_url": None,
        }

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            customer_email=email or None,
            success_url=f"{_FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{_FRONTEND_URL}/#pricing",
            metadata={"tier": tier, "hospital": hospital or ""},
            allow_promotion_codes=True,
        )
        return {"checkout_url": session.url, "session_id": session.id, "demo_mode": False}
    except Exception as e:
        return {"error": str(e), "checkout_url": None}


def handle_webhook(payload: bytes, sig_header: str) -> dict:
    if not STRIPE_WEBHOOK_SECRET:
        return {"status": "skipped", "reason": "no webhook secret configured"}

    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, Exception) as e:
        raise ValueError(f"Invalid webhook signature: {e}")

    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        return {
            "event": event_type,
            "customer_email": obj.get("customer_email"),
            "session_id": obj.get("id"),
            "subscription_id": obj.get("subscription"),
            "tier": obj.get("metadata", {}).get("tier", "starter"),
            "hospital": obj.get("metadata", {}).get("hospital", ""),
        }

    if event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        return {
            "event": event_type,
            "subscription_id": obj.get("id"),
            "status": obj.get("status"),
        }

    return {"event": event_type, "status": "ignored"}
