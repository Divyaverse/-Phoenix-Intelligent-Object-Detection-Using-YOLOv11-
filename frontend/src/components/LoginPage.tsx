import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

interface LoginPageProps {
  onBackToLanding?: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onBackToLanding }) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError('Please provide both authorized email address and security credential.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (err: any) {
      setError(err.message || 'Authorization failed. Please verify credentials or backend status.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0c0e12',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
        color: '#f4f4f5',
        padding: '20px',
      }}
    >
      {/* Top Brand Bar */}
      <div style={{ marginBottom: '28px', textAlign: 'center' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '44px',
            height: '44px',
            borderRadius: '4px',
            backgroundColor: '#dc2626',
            color: '#ffffff',
            fontWeight: 800,
            fontSize: '18px',
            marginBottom: '12px',
            boxShadow: '0 2px 10px rgba(220, 38, 38, 0.4)',
          }}
        >
          PX
        </div>
        <h1 style={{ fontSize: '20px', fontWeight: 800, margin: 0, color: '#fafafa', letterSpacing: '-0.3px' }}>
          PHOENIX CONTROL ROOM
        </h1>
        <p style={{ fontSize: '12px', color: '#71717a', marginTop: '4px', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
          Security & Life-Safety Intelligence Access
        </p>
      </div>

      {/* Terminal Card */}
      <div
        style={{
          width: '100%',
          maxWidth: '400px',
          backgroundColor: '#181b22',
          borderRadius: '6px',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
          padding: '28px',
          boxSizing: 'border-box',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', paddingBottom: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#a1a1aa', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            AUTHENTICATED ACCESS
          </span>
          <span style={{ fontSize: '10px', color: '#22c55e', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#22c55e' }} />
            AUTH SERVER ACTIVE
          </span>
        </div>

        {error && (
          <div
            style={{
              padding: '10px 12px',
              backgroundColor: 'rgba(220, 38, 38, 0.15)',
              border: '1px solid rgba(220, 38, 38, 0.4)',
              borderRadius: '4px',
              color: '#fca5a5',
              fontSize: '12px',
              marginBottom: '18px',
              lineHeight: 1.4,
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#d4d4d8', marginBottom: '6px' }}>
              Operator Identity (Email)
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. operator@facility.domain"
              required
              autoFocus
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: '4px',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                backgroundColor: '#0c0e12',
                color: '#ffffff',
                fontSize: '13px',
                outline: 'none',
                boxSizing: 'border-box',
                fontFamily: 'inherit',
              }}
            />
          </div>

          <div style={{ marginBottom: '22px' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#d4d4d8', marginBottom: '6px' }}>
              Security Key / Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: '4px',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                backgroundColor: '#0c0e12',
                color: '#ffffff',
                fontSize: '13px',
                outline: 'none',
                boxSizing: 'border-box',
                fontFamily: 'inherit',
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '11px',
              backgroundColor: '#dc2626',
              color: '#ffffff',
              border: 'none',
              borderRadius: '4px',
              fontSize: '13px',
              fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
              boxShadow: '0 2px 6px rgba(220, 38, 38, 0.3)',
              transition: 'background 0.2s',
            }}
          >
            {loading ? 'Verifying Authorization...' : 'Sign In to Control Room'}
          </button>
        </form>

          <div style={{ marginTop: '20px', borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '16px' }}>
            <div style={{ fontSize: '11px', color: '#71717a', marginBottom: '8px', fontWeight: 600 }}>
              Quick Demo Accounts:
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
              <button
                type="button"
                onClick={() => {
                  setEmail('admin@phoenix.local');
                  setPassword('AdminPass123!');
                }}
                style={{
                  padding: '6px 8px',
                  backgroundColor: '#0c0e12',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '3px',
                  color: '#f4f4f5',
                  fontSize: '11px',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                🔴 <strong>SuperAdmin</strong>
                <div style={{ fontSize: '9px', color: '#71717a' }}>admin@phoenix.local</div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setEmail('responder@phoenix.local');
                  setPassword('ResponderPass123!');
                }}
                style={{
                  padding: '6px 8px',
                  backgroundColor: '#0c0e12',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '3px',
                  color: '#f4f4f5',
                  fontSize: '11px',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                🚒 <strong>Responder</strong>
                <div style={{ fontSize: '9px', color: '#71717a' }}>responder@phoenix.local</div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setEmail('manager@phoenix.local');
                  setPassword('ManagerPass123!');
                }}
                style={{
                  padding: '6px 8px',
                  backgroundColor: '#0c0e12',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '3px',
                  color: '#f4f4f5',
                  fontSize: '11px',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                🏢 <strong>Building Mgr</strong>
                <div style={{ fontSize: '9px', color: '#71717a' }}>manager@phoenix.local</div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setEmail('occupant@phoenix.local');
                  setPassword('OccupantPass123!');
                }}
                style={{
                  padding: '6px 8px',
                  backgroundColor: '#0c0e12',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '3px',
                  color: '#f4f4f5',
                  fontSize: '11px',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                👤 <strong>Occupant</strong>
                <div style={{ fontSize: '9px', color: '#71717a' }}>occupant@phoenix.local</div>
              </button>
            </div>
          </div>

        {onBackToLanding && (
          <div style={{ marginTop: '16px', textAlign: 'center' }}>
            <button
              type="button"
              onClick={onBackToLanding}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#71717a',
                fontSize: '11px',
                cursor: 'pointer',
                textDecoration: 'underline',
              }}
            >
              ← Back to Phoenix Overview
            </button>
          </div>
        )}
      </div>

      <div style={{ marginTop: '24px', fontSize: '11px', color: '#52525b', textAlign: 'center' }}>
        Restricted to Authorized Life-Safety & Security Personnel
      </div>
    </div>
  );
};
