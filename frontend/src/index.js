import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import LoginPage from './LoginPage';
import { AuthProvider, useAuth } from './AuthContext';
import reportWebVitals from './reportWebVitals';

function Root() {
  const { user, loading } = useAuth();
  if (loading) return <div style={{ color: "#94a3b8", padding: 40, textAlign: "center" }}>Loading...</div>;
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
