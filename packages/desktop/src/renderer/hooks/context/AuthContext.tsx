import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { mutate } from 'swr';
import { PREVIEW_SCOPE_KEY_PREFIX } from '@/renderer/pages/conversation/Preview/context/previewScope';
import { refreshSession } from '@/common/adapter/sessionRefresh';
import {
  getSelfHostedBaseUrl,
  setSelfHostedBaseUrl,
  getSelfHostedToken,
  setSelfHostedToken,
  getSelfHostedUser,
  setSelfHostedUser,
  clearSelfHostedAuth,
} from '@/common/config/selfHosted';
import { configService } from '@/common/config/configService';
import { reportLog } from '@/common/logger/reportLog';

// M6: CSRF removed with legacy webserver — stub functions for compatibility, re-implement in M7
const withCsrfToken = <T extends Record<string, unknown>>(data: T): T => data;
const hasValidCsrfToken = (): boolean => true;
const clearCookie = (_name: string, _path?: string): void => {};
const CSRF_COOKIE_NAME = 'csrf-token';

type AuthStatus = 'checking' | 'authenticated' | 'unauthenticated';

export interface AuthUser {
  id: string;
  username: string;
  role?: string;
}

interface LoginParams {
  username: string;
  password: string;
  remember?: boolean;
  serverUrl?: string;
}

type LoginErrorCode =
  | 'invalidCredentials'
  | 'tooManyAttempts'
  | 'serverError'
  | 'networkError'
  | 'csrfError'
  | 'unknown';

interface LoginResult {
  success: boolean;
  message?: string;
  code?: LoginErrorCode;
  shouldClearCache?: boolean;
}

interface AuthContextValue {
  ready: boolean;
  user: AuthUser | null;
  status: AuthStatus;
  login: (params: LoginParams) => Promise<LoginResult>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  clearAuthCache: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const AUTH_USER_ENDPOINT = '/api/auth/user';

const isDesktopRuntime = typeof window !== 'undefined' && Boolean(window.electronAPI);

// Clear expired auth cache including cookies and localStorage
// 清除过期的认证缓存，包括 Cookie 和 localStorage
function clearAuthCache(): void {
  if (typeof window === 'undefined') return;

  try {
    // Clear CSRF cookie
    clearCookie(CSRF_COOKIE_NAME);
    clearCookie(CSRF_COOKIE_NAME, '/');

    // Clear localStorage auth-related items, plus per-user UI state that must not
    // leak across accounts. Preview scopes are keyed by project id and hold file
    // content, so leaving them behind would show the next user the previous one's
    // open tabs — and nothing else ever cleaned them up.
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (
        key &&
        (key.includes('auth') ||
          key.includes('csrf') ||
          key.includes('token') ||
          key.startsWith(PREVIEW_SCOPE_KEY_PREFIX))
      ) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach((key) => localStorage.removeItem(key));
  } catch (error) {
    console.error('Failed to clear auth cache:', error);
  }
}

async function fetchCurrentUser(signal?: AbortSignal): Promise<AuthUser | null> {
  try {
    let response = await fetch(AUTH_USER_ENDPOINT, {
      method: 'GET',
      credentials: 'include',
      signal,
    });

    // The access cookie may have expired — attempt one silent session refresh
    // and re-check before concluding the user is unauthenticated. Without this
    // the status poll would kick a refreshable session to /login (#4124).
    // refreshSession() single-flights with the httpBridge refresh path.
    if (response.status === 401) {
      const refreshed = await refreshSession();
      if (refreshed) {
        response = await fetch(AUTH_USER_ENDPOINT, {
          method: 'GET',
          credentials: 'include',
          signal,
        });
      }
    }

    if (!response.ok) {
      return null;
    }

    const data = (await response.json()) as {
      success: boolean;
      user?: AuthUser;
    };
    if (data.success && data.user) {
      return data.user;
    }
  } catch (error) {
    if ((error as Error).name === 'AbortError') {
      return null;
    }
    console.error('Failed to fetch current user:', error);
  }

  return null;
}

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>('checking');
  const [ready, setReady] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus('checking');

    // First check self-hosted JWT token if present
    const selfHostedToken = getSelfHostedToken();
    if (selfHostedToken) {
      try {
        const baseUrl = getSelfHostedBaseUrl();
        const response = await fetch(`${baseUrl}/api/auth/me`, {
          headers: {
            Authorization: `Bearer ${selfHostedToken}`,
          },
          signal: controller.signal,
        });
        if (response.ok) {
          const resJson = await response.json();
          if (resJson.code === 0 && resJson.data) {
            setUser({
              id: String(resJson.data.id),
              username: resJson.data.username,
              role: resJson.data.role,
            });
            setStatus('authenticated');
            setReady(true);
            void configService.syncFromSelfHosted().then((synced) => {
              if (synced) void mutate('providers');
            });
            return;
          }
        }
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.warn('Self-hosted auth verification failed:', err);
      }
      clearSelfHostedAuth();
    }

    if (isDesktopRuntime) {
      // In desktop runtime, unauthenticated state triggers login form for local account
      setUser(null);
      setStatus('unauthenticated');
      setReady(true);
      return;
    }

    const currentUser = await fetchCurrentUser(controller.signal);
    if (currentUser) {
      setUser(currentUser);
      setStatus('authenticated');
    } else {
      setUser(null);
      setStatus('unauthenticated');
    }
    setReady(true);
  }, []);

  useEffect(() => {
    void refresh();
    return () => {
      abortRef.current?.abort();
    };
  }, [refresh]);

  const login = useCallback(async ({ username, password, remember, serverUrl }: LoginParams): Promise<LoginResult> => {
    try {
      if (serverUrl) {
        setSelfHostedBaseUrl(serverUrl);
      }
      const baseUrl = getSelfHostedBaseUrl();

      // Try self-hosted backend login
      try {
        const response = await fetch(`${baseUrl}/api/auth/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ username, password }),
        });

        const data = await response.json();
        if (response.ok && data.code === 0 && data.data?.token) {
          const token = data.data.token;
          const userInfo = data.data.user;
          setSelfHostedToken(token);
          setSelfHostedUser(userInfo);
          setUser({
            id: String(userInfo.id),
            username: userInfo.username,
            role: userInfo.role,
          });
          setStatus('authenticated');
          setReady(true);
          reportLog('INFO', `User ${username} logged in successfully`);
          void configService.syncFromSelfHosted().then((synced) => {
            if (synced) void mutate('providers');
          });
          return { success: true };
        } else if (response.status === 401 || (data && data.code !== 0)) {
          return {
            success: false,
            message: data?.message || '用户名或密码错误',
            code: 'invalidCredentials',
          };
        }
      } catch (selfHostedError) {
        if (isDesktopRuntime) {
          console.error('Self-hosted server login failed:', selfHostedError);
          return {
            success: false,
            message: '无法连接到自托管服务器，请确认服务端已启动且地址正确',
            code: 'networkError',
          };
        }
      }

      if (isDesktopRuntime) {
        return {
          success: false,
          message: '登录失败，请检查自托管服务器连接',
          code: 'networkError',
        };
      }

      // Fallback for web mode
      const csrfTokenValid = hasValidCsrfToken();
      if (!csrfTokenValid) {
        clearAuthCache();
      }

      const response = await fetch('/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(withCsrfToken({ username, password, remember })),
      });

      const data = (await response.json()) as {
        success: boolean;
        message?: string;
        user?: AuthUser;
      };

      if (!response.ok || !data.success || !data.user) {
        return {
          success: false,
          message: data?.message ?? 'Login failed',
          code: response.status === 401 ? 'invalidCredentials' : 'serverError',
        };
      }

      setUser(data.user);
      setStatus('authenticated');
      setReady(true);

      return { success: true };
    } catch (error) {
      console.error('Login request failed:', error);
      return {
        success: false,
        message: 'Network error. Please try again.',
        code: 'networkError',
      };
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      const baseUrl = getSelfHostedBaseUrl();
      const token = getSelfHostedToken();
      if (token) {
        void fetch(`${baseUrl}/api/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        }).catch(() => {});
      }
      if (!isDesktopRuntime) {
        await fetch('/logout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(withCsrfToken({})),
        }).catch(() => {});
      }
    } finally {
      clearSelfHostedAuth();
      clearAuthCache();
      setUser(null);
      setStatus('unauthenticated');
      setReady(true);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ready,
      user,
      status,
      login,
      logout,
      refresh,
      clearAuthCache,
    }),
    [login, logout, ready, refresh, status, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
