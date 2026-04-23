import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import LoginPage from './LoginPage';
import LobbyDisplay from './LobbyDisplay';
import SymptomCheck from './SymptomCheck';
import { AuthProvider, useAuth } from './AuthContext';
import PatientPortal from './PatientPortal';
import reportWebVitals from './reportWebVitals';

function Root() {
  const { user, loading, warming } = useAuth();

  // Public routes — no auth required
  if (window.location.pathname === '/lobby') return <LobbyDisplay />;
  if (window.location.pathname === '/check') return <SymptomCheck />;
  if (window.location.pathname === '/patient') return <PatientPortal />;

  if (loading) {
    return (
      <div style={{
        minHeight: "100vh", background: "#050c18",
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        fontFamily: "'Inter', sans-serif", gap: 14,
      }}>
        <span style={{
          display: "inline-block", width: 36, height: 36,
          border: "3px solid #1e293b", borderTopColor: "#0d9488",
          borderRadius: "50%", animation: "spin 0.8s linear infinite",
        }} />
        <div style={{ color: "#3d5166", fontSize: 14 }}>
          {warming ? "Backend warming up — please wait a moment…" : "Loading MediScan…"}
        </div>
        {warming && (
          <div style={{
            color: "#1e4060", fontSize: 12, maxWidth: 280, textAlign: "center", lineHeight: 1.6,
          }}>
            The server is starting from sleep. This takes ~15 seconds on the free tier.
          </div>
        )}
      </div>
    );
  }

  return user ? <App /> : <LoginPage />;
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <AuthProvider>
      <Root />
    </AuthProvider>
  </React.StrictMode>
);

reportWebVitals();
