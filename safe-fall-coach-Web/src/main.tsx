import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AccessibilityProvider } from './context/AccessibilityContext';
import { AuthProvider } from './context/AuthContext';
import { RequireBackendConnection } from './components/RequireBackendConnection';
import './styles/globals.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <RequireBackendConnection>
      <AuthProvider>
        <AccessibilityProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AccessibilityProvider>
      </AuthProvider>
    </RequireBackendConnection>
  </React.StrictMode>
);