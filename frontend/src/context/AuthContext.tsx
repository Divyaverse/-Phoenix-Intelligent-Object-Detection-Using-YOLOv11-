import React, { createContext, useContext, useEffect, useState } from 'react';
import type { UserRole, UserResponse } from '../types/phoenix';
import { ApiClient } from '../services/apiClient';

interface AuthContextType {
  token: string | null;
  userId: string | null;
  role: UserRole | null;
  organizationId: string | null;
  userProfile: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  activeRoleView: UserRole;
  setActiveRoleView: (role: UserRole) => void;
  login: (email: string, password?: string) => Promise<void>;
  logout: () => void;
  authenticateAndSwitch: (targetRole: UserRole, credentials: { email: string; password: string }) => Promise<void>;
  switchAccount: (role: UserRole, credentials?: { email: string; password: string }) => Promise<void>;
  switchRole: (role: UserRole, credentials?: { email: string; password: string }) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(ApiClient.getToken());
  const [userId, setUserId] = useState<string | null>(localStorage.getItem('phoenix_user_id'));
  const [role, setRole] = useState<UserRole | null>((localStorage.getItem('phoenix_role') as UserRole) || null);
  const [organizationId, setOrganizationId] = useState<string | null>(localStorage.getItem('phoenix_org_id'));
  const [userProfile, setUserProfile] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [activeRoleView, setActiveRoleView] = useState<UserRole>(
    ((localStorage.getItem('phoenix_role') as UserRole) || 'BUILDING_MANAGER')
  );

  // Validate session against backend /auth/me on mount or token change
  useEffect(() => {
    let isMounted = true;
    const validateSession = async () => {
      const currentToken = ApiClient.getToken();
      if (!currentToken) {
        if (isMounted) {
          setIsLoading(false);
          setUserProfile(null);
        }
        return;
      }

      try {
        const profile = await ApiClient.getCurrentUser();
        if (isMounted) {
          setUserProfile(profile);
          setUserId(profile.user_id);
          setRole(profile.role);
          setOrganizationId(profile.organization_id);
          setActiveRoleView(profile.role);

          localStorage.setItem('phoenix_user_id', profile.user_id);
          localStorage.setItem('phoenix_role', profile.role);
          localStorage.setItem('phoenix_org_id', profile.organization_id);
        }
      } catch (err) {
        console.warn('Session verification failed; resetting expired credentials:', err);
        if (isMounted) {
          logout();
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    validateSession();

    const handleAuthExpired = () => {
      logout();
    };

    window.addEventListener('auth_expired', handleAuthExpired);
    return () => {
      isMounted = false;
      window.removeEventListener('auth_expired', handleAuthExpired);
    };
  }, []);

  const login = async (email: string, password?: string) => {
    setIsLoading(true);
    try {
      const res = await ApiClient.login({ email, password: password || '' });
      setToken(res.access_token);
      setUserId(res.user_id);
      setRole(res.role);
      setOrganizationId(res.organization_id);
      setActiveRoleView(res.role);

      localStorage.setItem('phoenix_user_id', res.user_id);
      localStorage.setItem('phoenix_role', res.role);
      localStorage.setItem('phoenix_org_id', res.organization_id);

      // Verify profile from backend
      const profile = await ApiClient.getCurrentUser();
      setUserProfile(profile);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Authenticated role transition:
   * 1. Does not mutate current active token or role upfront.
   * 2. Authenticates target credentials against /auth/login.
   * 3. Fetches /auth/me with newly issued token.
   * 4. Verifies the authenticated user profile matches the target role.
   * 5. Atomically switches active session if verification succeeds.
   * 6. Leaves existing session completely intact if authentication fails.
   */
  const authenticateAndSwitch = async (
    targetRole: UserRole,
    credentials: { email: string; password: string }
  ): Promise<void> => {
    const email = credentials.email.trim();
    const password = credentials.password;
    if (!email || !password) {
      throw new Error('Authorized email and password are required to switch roles.');
    }

    // 1. Authenticate with backend without touching current session
    const tokenRes = await ApiClient.authenticate({ email, password });

    // 2. Fetch authenticated profile from backend /auth/me
    const profile = await ApiClient.fetchProfileWithToken(tokenRes.access_token);

    // 3. Verify that the authenticated profile matches requested role
    if (profile.role !== targetRole) {
      throw new Error(
        `Role mismatch: Authenticated user "${profile.email}" has role ${profile.role}, not requested role ${targetRole}. Account switch rejected.`
      );
    }

    // 4. Invalidate prior session on backend
    if (token) {
      ApiClient.logoutUser().catch(() => {});
    }

    // 5. Atomically update active session state and local storage
    ApiClient.setToken(tokenRes.access_token);
    setToken(tokenRes.access_token);
    setUserId(profile.user_id);
    setRole(profile.role);
    setOrganizationId(profile.organization_id);
    setUserProfile(profile);
    setActiveRoleView(profile.role);

    localStorage.setItem('phoenix_user_id', profile.user_id);
    localStorage.setItem('phoenix_role', profile.role);
    localStorage.setItem('phoenix_org_id', profile.organization_id);
  };

  const switchAccount = async (targetRole: UserRole, credentials?: { email: string; password: string }) => {
    if (!credentials) {
      throw new Error('Direct role switching without authentication is prohibited. Please authenticate with valid credentials.');
    }
    return authenticateAndSwitch(targetRole, credentials);
  };

  const logout = () => {
    ApiClient.logoutUser().catch(() => {});
    setToken(null);
    setUserId(null);
    setRole(null);
    setOrganizationId(null);
    setUserProfile(null);
    localStorage.removeItem('phoenix_token');
    localStorage.removeItem('phoenix_user_id');
    localStorage.removeItem('phoenix_role');
    localStorage.removeItem('phoenix_org_id');
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        userId,
        role,
        organizationId,
        userProfile,
        isAuthenticated: !!token,
        isLoading,
        activeRoleView,
        setActiveRoleView,
        login,
        logout,
        authenticateAndSwitch,
        switchAccount,
        switchRole: switchAccount,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
