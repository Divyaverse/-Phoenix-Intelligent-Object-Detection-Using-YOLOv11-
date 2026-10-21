import React, { useState, useEffect } from 'react';
import type { UserRole } from '../types/phoenix';
import { useAuth } from '../context/AuthContext';

interface RoleAuthModalProps {
  isOpen: boolean;
  targetRole: UserRole | null;
  currentRole: UserRole | null;
  onClose: () => void;
  onSuccess: (newRole: UserRole) => void;
}

const ROLE_DISPLAY_NAMES: Record<UserRole, { label: string; icon: string; color: string; desc: string }> = {
  SUPERADMIN: {
    label: 'SuperAdmin',
    icon: '⚡',
    color: '#ef4444',
    desc: 'System-wide control, full database inspection, audit logs, and global user management.',
  },
  BUILDING_MANAGER: {
    label: 'Building Manager',
    icon: '🏢',
    color: '#3b82f6',
    desc: 'Facility telemetry, sensor calibration, CCTV oversight, and emergency dispatch.',
  },
  FIRST_RESPONDER: {
    label: 'First Responder',
    icon: '🚒',
    color: '#f97316',
    desc: 'Tactical egress paths, real-time hazard mapping, and priority life-safety routing.',
  },
  OCCUPANT: {
    label: 'Occupant',
    icon: '👤',
    color: '#10b981',
    desc: 'Individual safe routing, safety check-in, and emergency evacuation guidance.',
  },
};

export const RoleAuthModal: React.FC<RoleAuthModalProps> = ({
  isOpen,
  targetRole,
  currentRole,
  onClose,
  onSuccess,
}) => {
  const { authenticateAndSwitch } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Reset form inputs whenever modal opens or target role changes
  useEffect(() => {
    if (isOpen) {
      setEmail('');
      setPassword('');
      setErrorMessage(null);
      setIsSubmitting(false);
    }
  }, [isOpen, targetRole]);

  if (!isOpen || !targetRole) {
    return null;
  }

  const roleMeta = ROLE_DISPLAY_NAMES[targetRole] || {
    label: targetRole,
    icon: '🛡️',
    color: '#3b82f6',
    desc: 'Authorized life-safety access.',
  };

  const currentMeta = currentRole ? ROLE_DISPLAY_NAMES[currentRole] : null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail || !password) {
      setErrorMessage('Please enter both the target account email and password.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await authenticateAndSwitch(targetRole, { email: cleanEmail, password });
      onSuccess(targetRole);
    } catch (err: any) {
      // Retain original session, display clear error to user
      const msg = err?.message || 'Authentication failed. Please verify credentials.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !isSubmitting) {
      onClose();
    }
  };

  return (
    <div
      id="role-auth-modal-backdrop"
      onClick={handleBackdropClick}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.78)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '16px',
      }}
    >
      <div
        id="role-auth-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="role-auth-title"
        style={{
          width: '100%',
          maxWidth: '440px',
          backgroundColor: '#13161c',
          borderRadius: '8px',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.05)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          color: '#f4f4f5',
          fontFamily: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '16px 20px',
            backgroundColor: '#0d1015',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '28px',
                height: '28px',
                borderRadius: '4px',
                backgroundColor: 'rgba(220, 38, 38, 0.15)',
                color: '#ef4444',
                fontSize: '14px',
                border: '1px solid rgba(220, 38, 38, 0.3)',
              }}
            >
              🔒
            </span>
            <div>
              <h2
                id="role-auth-title"
                style={{
                  fontSize: '14px',
                  fontWeight: 700,
                  margin: 0,
                  letterSpacing: '0.3px',
                  color: '#ffffff',
                }}
              >
                Authenticate Role Switch
              </h2>
              <div style={{ fontSize: '11px', color: '#71717a' }}>
                Secure session credential verification
              </div>
            </div>
          </div>

          <button
            id="role-auth-close-x"
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            title="Cancel and close dialog"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#71717a',
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
              fontSize: '16px',
              padding: '4px 8px',
              borderRadius: '4px',
            }}
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px' }}>
          {/* Transition Context Banner */}
          <div
            style={{
              padding: '12px',
              backgroundColor: '#181b22',
              borderRadius: '6px',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              marginBottom: '16px',
              fontSize: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ color: '#71717a', fontSize: '11px', textTransform: 'uppercase', fontWeight: 600 }}>
                Target Privileges:
              </span>
              <span
                style={{
                  padding: '2px 8px',
                  borderRadius: '3px',
                  fontSize: '11px',
                  fontWeight: 700,
                  backgroundColor: `${roleMeta.color}22`,
                  color: roleMeta.color,
                  border: `1px solid ${roleMeta.color}44`,
                }}
              >
                {roleMeta.icon} {roleMeta.label}
              </span>
            </div>

            <div style={{ fontSize: '11px', color: '#94a3b8', lineHeight: 1.4 }}>
              {roleMeta.desc}
            </div>

            {currentMeta && (
              <div
                style={{
                  marginTop: '8px',
                  paddingTop: '8px',
                  borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                  fontSize: '11px',
                  color: '#64748b',
                  display: 'flex',
                  justifyContent: 'space-between',
                }}
              >
                <span>Current Active Session:</span>
                <span style={{ color: '#cbd5e1', fontWeight: 600 }}>
                  {currentMeta.icon} {currentMeta.label}
                </span>
              </div>
            )}
          </div>

          <p style={{ fontSize: '12px', color: '#a1a1aa', margin: '0 0 16px 0', lineHeight: 1.4 }}>
            In accordance with PHOENIX security policy, a role button cannot grant or switch privileges by itself.
            Please enter the credentials for an authorized account with the <strong>{roleMeta.label}</strong> role.
          </p>

          {/* Error Banner */}
          {errorMessage && (
            <div
              id="role-auth-error"
              style={{
                padding: '10px 12px',
                backgroundColor: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                borderRadius: '5px',
                color: '#fca5a5',
                fontSize: '12px',
                marginBottom: '16px',
                lineHeight: 1.4,
              }}
            >
              <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <span>⚠️</span> Authentication Denied
              </div>
              <div>{errorMessage}</div>
            </div>
          )}

          {/* Credential Form */}
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '14px' }}>
              <label
                htmlFor="role-auth-email"
                style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#d4d4d8', marginBottom: '6px' }}
              >
                Account Email
              </label>
              <input
                id="role-auth-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. operator@phoenix.local"
                required
                autoFocus
                disabled={isSubmitting}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '4px',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  backgroundColor: '#0c0e12',
                  color: '#ffffff',
                  fontSize: '13px',
                  outline: 'none',
                  boxSizing: 'border-box',
                  fontFamily: 'inherit',
                  opacity: isSubmitting ? 0.6 : 1,
                }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label
                htmlFor="role-auth-password"
                style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#d4d4d8', marginBottom: '6px' }}
              >
                Account Password
              </label>
              <input
                id="role-auth-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                required
                disabled={isSubmitting}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '4px',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  backgroundColor: '#0c0e12',
                  color: '#ffffff',
                  fontSize: '13px',
                  outline: 'none',
                  boxSizing: 'border-box',
                  fontFamily: 'inherit',
                  opacity: isSubmitting ? 0.6 : 1,
                }}
              />
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button
                id="role-auth-cancel"
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#27272a',
                  color: '#d4d4d8',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: isSubmitting ? 'not-allowed' : 'pointer',
                  opacity: isSubmitting ? 0.6 : 1,
                }}
              >
                Cancel
              </button>

              <button
                id="role-auth-submit"
                type="submit"
                disabled={isSubmitting || !email.trim() || !password}
                style={{
                  padding: '8px 18px',
                  backgroundColor: isSubmitting || !email.trim() || !password ? '#374151' : '#2563eb',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: isSubmitting || !email.trim() || !password ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: isSubmitting ? 'none' : '0 2px 6px rgba(37, 99, 235, 0.4)',
                  transition: 'background 0.15s ease',
                }}
              >
                {isSubmitting ? (
                  <>
                    <span
                      style={{
                        display: 'inline-block',
                        width: '12px',
                        height: '12px',
                        border: '2px solid rgba(255, 255, 255, 0.3)',
                        borderTopColor: '#ffffff',
                        borderRadius: '50%',
                        animation: 'spin 0.8s linear infinite',
                      }}
                    />
                    Authenticating...
                  </>
                ) : (
                  <>Authenticate & Switch</>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
