import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";
const AuthContext = createContext(null);

const TOKEN_VALIDATE_TIMEOUT_MS = 8000;
const REFRESH_BEFORE_EXPIRY_MS = 5 * 60 * 1000; // refresh 5 min before expiry

function decodeTokenPayload(token) {
  try {
    return JSON.parse(atob(token.split(".")[1]));
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [warming, setWarming] = useState(false);
  const refreshTimerRef = useRef(null);

  const logout = useCallback(() => {
    clearTimeout(refreshTimerRef.current);
    localStorage.removeItem("mediscan_token");
    setUser(null);
  }, []);

  const scheduleRefresh = useCallback((token) => {
    clearTimeout(refreshTimerRef.current);
    const payload = decodeTokenPayload(token);
    if (!payload?.exp) return;

    const expiresAt = payload.exp * 1000;
    const delay = Math.max(10_000, expiresAt - Date.now() - REFRESH_BEFORE_EXPIRY_MS);

    refreshTimerRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) { logout(); return; }
        const data = await res.json();
        const newToken = data.access_token;
        localStorage.setItem("mediscan_token", newToken);
        setUser(prev => prev ? { ...prev, token: newToken } : prev);
        scheduleRefresh(newToken);
      } catch {
        // Network blip — token still valid; will retry on next page load
      }
    }, delay);
  }, [logout]);

  // Validate stored token on load
  useEffect(() => {
    const token = localStorage.getItem("mediscan_token");
    if (!token) { setLoading(false); return; }

    const controller = new AbortController();
    const warmTimer = setTimeout(() => setWarming(true), 2500);
    const killTimer = setTimeout(() => controller.abort(), TOKEN_VALIDATE_TIMEOUT_MS);

    fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => {
        setUser({ ...data, token });
        scheduleRefresh(token);
      })
      .catch(logout)
      .finally(() => {
        clearTimeout(warmTimer);
        clearTimeout(killTimer);
        setLoading(false);
        setWarming(false);
      });

    return () => {
      clearTimeout(warmTimer);
      clearTimeout(killTimer);
      controller.abort();
    };
  }, [logout, scheduleRefresh]);

  const login = async (username, password, totp_code = undefined) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, ...(totp_code ? { totp_code } : {}) }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    if (data.mfa_required) return data;
    localStorage.setItem("mediscan_token", data.access_token);
    setUser({ username, role: data.role, name: data.name, token: data.access_token });
    scheduleRefresh(data.access_token);
    return data;
  };

  const loginWithToken = (accessToken) => {
    const payload = decodeTokenPayload(accessToken);
    localStorage.setItem("mediscan_token", accessToken);
    setUser({
      username: payload.sub || "demo",
      role: payload.role || "physician",
      name: payload.sub === "demo" ? "Demo User" : payload.sub,
      token: accessToken,
    });
    scheduleRefresh(accessToken);
  };

  return (
    <AuthContext.Provider value={{ user, login, loginWithToken, logout, loading, warming }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
export { API_BASE };
