"""
MediScan CareNavigator — AI symptom assessment engine.
Improved over ClearStep: Claude claude-sonnet-4-6 with extended thinking replaces
rule-based Schmitt-Thompson protocols. Capacity-aware routing, transparent reasoning,
pre-arrival ED handoff, voice/image input support.
"""
import os
import json
import hashlib
import time
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── Assessment cache — avoids re-running identical inputs ─────────────────────
_assessment_cache: dict = {}      # key → {"result": dict, "expires": float}
_CACHE_TTL_SECONDS = 1800         # 30-minute TTL; identical symptom inputs share result


def _cache_key(age: int, sex: str, symptoms: str, risk_factors: list, qa_history: list) -> str:
    raw = f"{age}|{sex}|{symptoms.strip().lower()}|{','.join(sorted(risk_factors))}|{json.dumps(qa_history, sort_keys=True)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _adaptive_budget(symptoms: str, risk_factors: list, qa_history: list) -> int:
    """Scale thinking budget by case complexity to minimize token burn."""
    complexity = 0
    sym_lower = symptoms.lower()
    # High-acuity keywords → maximum reasoning
    high_acuity = ["chest pain", "shortness of breath", "stroke", "seizure", "unconscious",
                   "severe", "worst headache", "blood", "pregnant", "cardiac", "sepsis"]
    if any(k in sym_lower for k in high_acuity):
        complexity += 3
    # Each risk factor adds complexity
    complexity += min(len(risk_factors), 4)
    # Q&A history means second-pass — needs deeper synthesis
    if qa_history:
        complexity += 2
    # Long symptom description → more complexity
    if len(symptoms) > 200:
        complexity += 1

    if complexity >= 5:
        return 3000   # complex: full reasoning budget
    if complexity >= 2:
        return 1500   # moderate
    return 800        # simple

CARE_LEVELS = {
    "CALL_911": {
        "label": "Call 911 Immediately",
        "sub": "Life-threatening emergency",
        "color": "#dc2626",
        "bg": "#fef2f2",
        "icon": "🚨",
        "urgency": 0,
        "action": "Call 911 now or have someone take you to the nearest emergency room. Do not drive yourself.",
    },
    "ED_NOW": {
        "label": "Go to Emergency Room Now",
        "sub": "Requires immediate evaluation",
        "color": "#ea580c",
        "bg": "#fff7ed",
        "icon": "🔴",
        "urgency": 1,
        "action": "Go to the emergency room immediately. If symptoms worsen rapidly, call 911.",
    },
    "ED_SOON": {
        "label": "Emergency Room — Within 1–2 Hours",
        "sub": "Urgent but not immediately life-threatening",
        "color": "#f97316",
        "bg": "#fff7ed",
        "icon": "🟠",
        "urgency": 2,
        "action": "Seek emergency care within the next 1–2 hours. Monitor for any worsening.",
    },
    "URGENT_CARE": {
        "label": "Urgent Care — Today",
        "sub": "Should be seen within hours",
        "color": "#eab308",
        "bg": "#fefce8",
        "icon": "🟡",
        "urgency": 3,
        "action": "Visit an urgent care center or call your doctor's office for a same-day appointment.",
    },
    "TELEHEALTH": {
        "label": "Telehealth Visit",
        "sub": "Virtual visit appropriate",
        "color": "#0d9488",
        "bg": "#f0fdfa",
        "icon": "💻",
        "urgency": 4,
        "action": "Schedule a telehealth appointment today. This can be evaluated via video call.",
    },
    "PRIMARY_CARE": {
        "label": "Schedule with Your Doctor",
        "sub": "Routine appointment within 1–3 days",
        "color": "#16a34a",
        "bg": "#f0fdf4",
        "icon": "🩺",
        "urgency": 5,
        "action": "Schedule an appointment with your primary care provider within the next 1–3 days.",
    },
    "SELF_CARE": {
        "label": "Self-Care at Home",
        "sub": "Manageable without immediate medical care",
        "color": "#6b7280",
        "bg": "#f9fafb",
        "icon": "🏠",
        "urgency": 6,
        "action": "You can manage this at home. Follow the guidance below and monitor your symptoms.",
    },
}


def build_assessment_prompt(
    age: int,
    sex: str,
    symptoms: str,
    risk_factors: list,
    qa_history: list,
    ed_occupancy_pct: float = 0,
    language: str = "English",
) -> str:
    qa_text = ""
    if qa_history:
        qa_text = "\n\nFOLLOW-UP Q&A:\n"
        for item in qa_history:
            qa_text += f"Q: {item['question']}\nA: {item['answer']}\n"

    capacity_note = ""
    if ed_occupancy_pct >= 90:
        capacity_note = f"\n\nIMPORTANT — LOCAL ED CAPACITY: The nearest ED is currently at {ed_occupancy_pct}% capacity (surge). " \
                        "Unless the patient requires immediate emergency intervention, prefer URGENT_CARE over ED_SOON."

    rf_text = ", ".join(risk_factors) if risk_factors else "None reported"

    return f"""You are MediScan CareNavigator — the world's most advanced AI clinical triage assistant.
A patient is at home and needs guidance on whether and where to seek care.
Respond only in {language}.

═══════════════════════════════════════════════
PATIENT CONTEXT
═══════════════════════════════════════════════
Age: {age}
Biological Sex: {sex}
Presenting Symptoms: {symptoms}
Known Risk Factors / Conditions: {rf_text}{qa_text}{capacity_note}

═══════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════
1. Perform a thorough clinical assessment using all available information.
2. Apply validated clinical decision rules where relevant:
   - HEART score for chest pain
   - Ottawa rules for ankle/knee injuries
   - ABCD² for TIA
   - Wells criteria for DVT/PE
   - Cincinnati Stroke Scale (FAST) for neuro symptoms
   - PSI/PORT for respiratory illness severity
   - PECARN for pediatric head trauma (if age < 18)
3. Identify RED FLAG symptoms that require immediate escalation.
4. If you need more information to make a safe recommendation, ask up to 4 targeted clinical questions.
5. For patients ≥65 or with cardiac/neurological symptoms, apply age-adjusted thresholds — older adults frequently under-report severity.
6. For pediatric patients (age <18), apply PECARN, Pediatric Appendicitis Score, and age-appropriate vital sign norms.
7. Check for red flags that ALWAYS require at least ED_SOON regardless of other factors: sudden severe headache ("thunderclap"), unilateral weakness/slurred speech, chest pain radiating to arm/jaw, signs of sepsis (fever+altered mental status+rapid HR), signs of PE (sudden dyspnea+pleuritic chest pain+leg swelling), hematemesis/melena, priapism, sudden vision loss.
8. If you have sufficient information, provide the final care recommendation.

═══════════════════════════════════════════════
OUTPUT — VALID JSON ONLY, NO MARKDOWN
═══════════════════════════════════════════════
If more info needed:
{{
  "status": "needs_info",
  "questions": [
    {{"id": "q1", "text": "question text", "type": "yesno|scale|text|choice", "options": ["opt1","opt2"]}}
  ],
  "preliminary_concern": "one-line preliminary assessment"
}}

If sufficient info:
{{
  "status": "complete",
  "care_level": "CALL_911|ED_NOW|ED_SOON|URGENT_CARE|TELEHEALTH|PRIMARY_CARE|SELF_CARE",
  "headline": "One concise sentence explaining what this likely is",
  "reasoning": "2-3 sentences explaining WHY this care level was chosen, with clinical rationale",
  "red_flags": ["symptom that would escalate care level immediately"],
  "self_care_steps": ["actionable step 1", "actionable step 2"],
  "follow_up_timeframe": "when to re-evaluate if no improvement",
  "clinical_scores": {{}},
  "differential_dx": ["top 3 possibilities to rule out"],
  "medications_to_avoid": ["medication/class to avoid given symptoms — empty list if none"],
  "ed_ready_summary": "one-line summary for ED triage nurse if patient comes in"
}}"""


def run_assessment(
    age: int,
    sex: str,
    symptoms: str,
    risk_factors: list,
    qa_history: list,
    ed_occupancy_pct: float = 0,
    language: str = "English",
) -> dict:
    """Synchronous single-call assessment. Returns parsed JSON dict."""
    # Cache check — skip AI call for identical inputs within TTL
    ck = _cache_key(age, sex, symptoms, risk_factors, qa_history)
    cached = _assessment_cache.get(ck)
    if cached and cached["expires"] > time.time():
        return cached["result"]

    budget = _adaptive_budget(symptoms, risk_factors, qa_history)
    prompt = build_assessment_prompt(age, sex, symptoms, risk_factors, qa_history, ed_occupancy_pct, language)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max(1500, budget),
            thinking={"type": "enabled", "budget_tokens": budget},
            messages=[{"role": "user", "content": prompt}],
        )
        text = next((b.text for b in response.content if hasattr(b, "text")), "{}")
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())

        # Attach care level metadata
        if result.get("status") == "complete":
            level = result.get("care_level", "SELF_CARE")
            result["care_level_meta"] = CARE_LEVELS.get(level, CARE_LEVELS["SELF_CARE"])

        # Cache result (don't cache needs_info — those are stateful)
        if result.get("status") == "complete":
            _assessment_cache[ck] = {"result": result, "expires": time.time() + _CACHE_TTL_SECONDS}
            # Prune cache if it grows large
            if len(_assessment_cache) > 500:
                now = time.time()
                expired = [k for k, v in _assessment_cache.items() if v["expires"] < now]
                for k in expired:
                    _assessment_cache.pop(k, None)

        return result
    except Exception as e:
        print(f"CareNavigator error: {e}")
        return _fallback_assessment(age, symptoms)


def _fallback_assessment(age: int, symptoms: str) -> dict:
    c = symptoms.lower()
    if any(k in c for k in ["chest pain", "not breathing", "unresponsive", "cardiac arrest", "stroke"]):
        level = "CALL_911"
    elif any(k in c for k in ["shortness of breath", "severe", "allergic", "unconscious"]):
        level = "ED_NOW"
    elif any(k in c for k in ["moderate", "high fever", "injury", "abdominal"]):
        level = "URGENT_CARE"
    else:
        level = "PRIMARY_CARE"
    return {
        "status": "complete",
        "care_level": level,
        "headline": f"Based on reported symptoms: {symptoms[:60]}",
        "reasoning": "Assessment performed using baseline clinical rules. For best results, ensure AI service is configured.",
        "red_flags": [],
        "self_care_steps": [],
        "follow_up_timeframe": "24 hours",
        "differential_dx": [],
        "ed_ready_summary": symptoms[:100],
        "care_level_meta": CARE_LEVELS.get(level, CARE_LEVELS["PRIMARY_CARE"]),
    }
