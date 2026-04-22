import { createContext, useContext, useState, useEffect, useCallback } from "react";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";
const AuthContext = createContext(null);

const TOKEN_VALIDATE_TIMEOUT_MS = 8000; // Render free tier needs up to ~30s cold start; we abort at 8s and clear the token

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [warming, setWarming] = useState(false);

  const logout = useCallback(() => {
    localStorage.removeItem("mediscan_token");
    setUser(null);
  }, []);

  // Validate stored token on load — with timeout so a sleeping Render instance
  // doesn't leave the app stuck on the loading spinner forever.
  useEffect(() => {
    const token = localStorage.getItem("mediscan_token");
    if (!token) { setLoading(false); return; }

    const controller = new AbortController();
    // After 2.5s still loading → show "warming up" message
    const warmTimer = setTimeout(() => setWarming(true), 2500);
    // Hard abort at 8s → treat as logged-out
    const killTimer = setTimeout(() => controller.abort(), TOKEN_VALIDATE_TIMEOUT_MS);

    fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => setUser({ ...data, token }))
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
  }, [logout]);

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
    return data;
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, warming }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
export { API_BASE };
