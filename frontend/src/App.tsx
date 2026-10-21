import React, { Component, type ErrorInfo, type ReactNode, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import { LandingPage } from './components/LandingPage';
import { LoginPage } from './components/LoginPage';
import { DashboardPage } from './components/DashboardPage';
import './App.css';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('PHOENIX UI Render Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '32px', backgroundColor: '#0c0e12', color: '#fca5a5', minHeight: '100vh', fontFamily: 'sans-serif' }}>
          <h2>⚠️ PHOENIX Dashboard Runtime Notice</h2>
          <pre style={{ backgroundColor: '#181b22', padding: '16px', borderRadius: '4px', overflow: 'auto', border: '1px solid #dc2626' }}>
            {this.state.error?.message}
          </pre>
          <button
            onClick={() => {
              localStorage.clear();
              window.location.reload();
            }}
            style={{ padding: '8px 16px', backgroundColor: '#dc2626', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', marginTop: '16px' }}
          >
            Reset Session & Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const MainContent: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [showLogin, setShowLogin] = useState<boolean>(false);

  // If authenticated, enter control room directly
  if (isAuthenticated) {
    return (
      <WebSocketProvider buildingId="bldg-hq-01">
        <DashboardPage />
      </WebSocketProvider>
    );
  }

  // If user clicked to enter control room, show dedicated login terminal
  if (showLogin) {
    return <LoginPage onBackToLanding={() => setShowLogin(false)} />;
  }

  // Otherwise, render dedicated Phoenix Landing Page
  return <LandingPage onEnterControlRoom={() => setShowLogin(true)} />;
};

export function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <MainContent />
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;

