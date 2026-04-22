import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import LoginPage from './LoginPage';
import LobbyDisplay from './LobbyDisplay';
import { AuthProvider, useAuth } from './AuthContext';
import reportWebVitals from './reportWebVitals';

function Root() {
  const { user, loading } = useAuth();

  // Public lobby display — no auth required
  if (window.location.pathname === '/lobby') {
    return <LobbyDisplay />;
  }

  if (loading) {
    return (
      <div style={{
        minHeight: "100vh",
        background: "#050c18",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "#3d5166",
        fontFamily: "'Inter', sans-serif",
        fontSize: 14,
        gap: 10,
      }}>
        <span style={{
          display: "inline-block",
          width: 16, height: 16,
          border: "2px solid #3d5166",
          borderTopColor: "#0d9488",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
        }} />
        Loading MediScan…
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
