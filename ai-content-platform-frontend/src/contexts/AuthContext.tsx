import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import { apiClient, ensureAccessToken } from '@/api/client';
import type { User, LoginRequest, ApiEnvelope } from '@/api/types';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

interface TokenPayload {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
}

interface MePayload {
  user_id: string;
  email: string;
  display_name: string;
  organization_id: string;
  role: string;
}

function mapUser(payload: MePayload): User {
  return {
    id: payload.user_id,
    email: payload.email,
    name: payload.display_name,
    role: (payload.role as User['role']) || 'editor',
    organization_id: payload.organization_id,
    created_at: new Date().toISOString(),
  };
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/** Deduplicate concurrent /auth/me calls (React StrictMode double-mount). */
let inflightMe: Promise<MePayload> | null = null;

async function fetchMe(): Promise<MePayload> {
  if (!inflightMe) {
    inflightMe = apiClient
      .get<ApiEnvelope<MePayload>>('/auth/me')
      .then((response) => {
        const payload = response.data.data;
        if (!payload) throw new Error('Empty /auth/me response');
        return payload;
      })
      .finally(() => {
        inflightMe = null;
      });
  }
  return inflightMe;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: !!localStorage.getItem('access_token'),
    isLoading: true,
  });
  const bootstrapped = useRef(false);

  const refreshUser = useCallback(async () => {
    const token = await ensureAccessToken();
    if (!token) {
      setState({ user: null, isAuthenticated: false, isLoading: false });
      return;
    }
    try {
      const payload = await fetchMe();
      const user = mapUser(payload);
      localStorage.setItem('user', JSON.stringify(user));
      setState({ user, isAuthenticated: true, isLoading: false });
    } catch {
      // apiClient already tried /auth/refresh on 401; session is gone.
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      setState({ user: null, isAuthenticated: false, isLoading: false });
    }
  }, []);

  const login = useCallback(async (credentials: LoginRequest) => {
    const response = await apiClient.post<ApiEnvelope<TokenPayload>>('/auth/login', credentials);
    const token = response.data.data?.access_token;
    if (!token) {
      throw new Error(response.data.error || 'Login failed');
    }
    localStorage.setItem('access_token', token);
    if (response.data.data?.refresh_token) {
      localStorage.setItem('refresh_token', response.data.data.refresh_token);
    }
    await refreshUser();
  }, [refreshUser]);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    setState({ user: null, isAuthenticated: false, isLoading: false });
  }, []);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    void refreshUser();
  }, [refreshUser]);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
