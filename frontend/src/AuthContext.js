import { createContext, useContext, useState, useEffect, useCallback } from "react";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem("mediscan_token");
    setUser(null);
  }, []);

  // Validate stored token on load
  useEffect(() => {
    const token = localStorage.getItem("mediscan_token");
    if (!token) { setLoading(false); return; }

    fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => setUser({ ...data, token }))
      .catch(logout)
      .finally(() => setLoading(false));
  }, [logout]);

  const login = async (username, password) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    localStorage.setItem("mediscan_token", data.access_token);
    setUser({ username, role: data.role, name: data.name, token: data.access_token });
    return data;
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
export { API_BASE };
