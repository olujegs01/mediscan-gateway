"""
Epic FHIR R4 client — OAuth2 client_credentials flow.

Set env vars to enable real Epic sandbox:
  EPIC_CLIENT_ID     — from open.epic.com app registration
  EPIC_TOKEN_URL     — https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
  EPIC_FHIR_BASE     — https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4

Without these, every call falls through to the simulated biometric.py data.
"""
import os
import time
import httpx

_CLIENT_ID   = os.getenv("EPIC_CLIENT_ID", "")
_TOKEN_URL   = os.getenv("EPIC_TOKEN_URL", "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token")
_FHIR_BASE   = os.getenv("EPIC_FHIR_BASE", "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4")

# Public sandbox — no auth required, used when Epic creds are absent
_SANDBOX_BASE = os.getenv("FHIR_SANDBOX_URL", "https://hapi.fhir.org/baseR4")

_token_cache: dict = {"token": None, "expires_at": 0}


def _get_token() -> str | None:
    if not _CLIENT_ID:
        return None
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 30:
        return _token_cache["token"]
    try:
        r = httpx.post(_TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": _CLIENT_ID,
            "scope": "system/Patient.read system/Observation.read",
        }, timeout=10)
        r.raise_for_status()
        j = r.json()
        _token_cache["token"] = j["access_token"]
        _token_cache["expires_at"] = now + j.get("expires_in", 3600)
        return _token_cache["token"]
    except Exception as e:
        print(f"[FHIR] Token fetch error: {e}")
        return None


def search_patient_sandbox(name: str) -> dict | None:
    """Public HAPI FHIR R4 sandbox lookup — no auth, used for demo."""
    parts = name.strip().split()
    params = {"_count": "1", "_format": "json"}
    if len(parts) >= 2:
        params["given"] = parts[0]
        params["family"] = parts[-1]
    else:
        params["name"] = name
    try:
        r = httpx.get(
            f"{_SANDBOX_BASE}/Patient",
            params=params,
            headers={"Accept": "application/fhir+json"},
            timeout=6,
        )
        if r.status_code != 200:
            return None
        bundle = r.json()
        entries = bundle.get("entry", [])
        if not entries:
            return None
        return _parse_patient(entries[0]["resource"])
    except Exception as e:
        print(f"[FHIR sandbox] search error: {e}")
        return None


def search_patient(name: str, dob: str = None) -> dict | None:
    """
    Search for a Patient by name (and optionally DOB).
    Returns a simplified dict or None if not found / not configured.
    """
    token = _get_token()
    if not token:
        return search_patient_sandbox(name)  # fall through to public sandbox

    parts = name.strip().split()
    params = {"_count": "1"}
    if len(parts) >= 2:
        params["given"] = parts[0]
        params["family"] = parts[-1]
    else:
        params["name"] = name
    if dob:
        params["birthdate"] = dob

    try:
        r = httpx.get(
            f"{_FHIR_BASE}/Patient",
            params=params,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"},
            timeout=8,
        )
        r.raise_for_status()
        bundle = r.json()
        entries = bundle.get("entry", [])
        if not entries:
            return None
        res = entries[0]["resource"]
        return _parse_patient(res)
    except Exception as e:
        print(f"[FHIR] Patient search error: {e}")
        return None


def get_conditions(fhir_patient_id: str) -> list[str]:
    """Pull active condition names for a patient."""
    token = _get_token()
    if not token or not fhir_patient_id:
        return []
    try:
        r = httpx.get(
            f"{_FHIR_BASE}/Condition",
            params={"patient": fhir_patient_id, "clinical-status": "active", "_count": "20"},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"},
            timeout=8,
        )
        r.raise_for_status()
        bundle = r.json()
        conditions = []
        for entry in bundle.get("entry", []):
            res = entry["resource"]
            code = res.get("code", {})
            text = code.get("text") or (code.get("coding", [{}])[0].get("display", ""))
            if text:
                conditions.append(text)
        return conditions
    except Exception as e:
        print(f"[FHIR] Conditions error: {e}")
        return []


def get_medications(fhir_patient_id: str) -> list[str]:
    """Pull active medication names."""
    token = _get_token()
    if not token or not fhir_patient_id:
        return []
    try:
        r = httpx.get(
            f"{_FHIR_BASE}/MedicationRequest",
            params={"patient": fhir_patient_id, "status": "active", "_count": "20"},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"},
            timeout=8,
        )
        r.raise_for_status()
        bundle = r.json()
        meds = []
        for entry in bundle.get("entry", []):
            res = entry["resource"]
            mc = res.get("medicationCodeableConcept", {})
            text = mc.get("text") or (mc.get("coding", [{}])[0].get("display", ""))
            if text:
                meds.append(text)
        return meds
    except Exception as e:
        print(f"[FHIR] Medications error: {e}")
        return []


def _parse_patient(res: dict) -> dict:
    fhir_id = res.get("id", "")
    name_list = res.get("name", [{}])
    official = next((n for n in name_list if n.get("use") == "official"), name_list[0] if name_list else {})
    given = " ".join(official.get("given", []))
    family = official.get("family", "")
    full_name = f"{given} {family}".strip()

    dob = res.get("birthDate", "")
    blood_type = ""

    telecom = res.get("telecom", [])
    phone = next((t["value"] for t in telecom if t.get("system") == "phone"), None)

    return {
        "fhir_id": fhir_id,
        "name": full_name,
        "dob": dob,
        "blood_type": blood_type,
        "phone": phone,
    }


def fhir_available() -> bool:
    return True  # sandbox always available; Epic active only when CLIENT_ID set


def fhir_mode() -> str:
    return "epic" if _CLIENT_ID else "sandbox"
