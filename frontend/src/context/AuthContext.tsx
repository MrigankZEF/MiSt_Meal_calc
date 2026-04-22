/**
 * AuthContext — global auth state for MiSt.
 *
 * Token is persisted in localStorage under MIST_TOKEN_KEY.
 * On mount we try to verify any stored token via /auth/users/me.
 * If it's expired or invalid we clear it silently.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';

import { getCurrentUser, loginUser, registerUser } from '../api/client';
import type { UserOut } from '../api/types';

const MIST_TOKEN_KEY = 'mist_token';

// ── Context type ──────────────────────────────────────────────────────────

export interface AuthContextValue {
  /** null = not logged in */
  user: UserOut | null;
  /** Raw JWT bearer token */
  token: string | null;
  /** True while the initial token-verification fetch is in flight */
  isLoading: boolean;
  /** Log in with email + password. Throws on failure. */
  login: (email: string, password: string) => Promise<void>;
  /** Register a new account, then immediately log in. Throws on failure. */
  register: (email: string, password: string, fullName: string) => Promise<void>;
  /** Clear token and user from memory + storage. */
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem(MIST_TOKEN_KEY),
  );
  const [isLoading, setIsLoading] = useState(true);

  // On mount: verify any stored token.
  useEffect(() => {
    const stored = localStorage.getItem(MIST_TOKEN_KEY);
    if (!stored) {
      setIsLoading(false);
      return;
    }
    getCurrentUser(stored)
      .then(me => {
        setUser(me);
        setToken(stored);
      })
      .catch(() => {
        localStorage.removeItem(MIST_TOKEN_KEY);
        setToken(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await loginUser(email, password);
    localStorage.setItem(MIST_TOKEN_KEY, access_token);
    setToken(access_token);
    const me = await getCurrentUser(access_token);
    setUser(me);
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      await registerUser(email, password, fullName);
      // Auto-login immediately after registration.
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(MIST_TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
