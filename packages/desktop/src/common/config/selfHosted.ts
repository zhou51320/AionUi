/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

export const SELF_HOSTED_BASE_KEY = 'self_hosted_base_url';
export const SELF_HOSTED_TOKEN_KEY = 'self_hosted_jwt_token';
export const SELF_HOSTED_USER_KEY = 'self_hosted_user_info';
export const DEFAULT_SELF_HOSTED_BASE = 'http://127.0.0.1:5000';

export interface SelfHostedUser {
  id: number | string;
  username: string;
  role: 'admin' | 'user' | string;
}

export function getSelfHostedBaseUrl(): string {
  if (typeof window !== 'undefined' && window.localStorage) {
    const custom = window.localStorage.getItem(SELF_HOSTED_BASE_KEY);
    if (custom && custom.trim()) {
      return custom.trim().replace(/\/+$/, '');
    }
  }
  if (typeof process !== 'undefined' && process.env && process.env.SELF_HOSTED_BASE) {
    return process.env.SELF_HOSTED_BASE.trim().replace(/\/+$/, '');
  }
  return DEFAULT_SELF_HOSTED_BASE;
}

export function setSelfHostedBaseUrl(url: string): void {
  if (typeof window !== 'undefined' && window.localStorage) {
    const trimmed = url.trim().replace(/\/+$/, '');
    if (trimmed) {
      window.localStorage.setItem(SELF_HOSTED_BASE_KEY, trimmed);
    } else {
      window.localStorage.removeItem(SELF_HOSTED_BASE_KEY);
    }
  }
}

export function getSelfHostedToken(): string | null {
  if (typeof window !== 'undefined' && window.localStorage) {
    return window.localStorage.getItem(SELF_HOSTED_TOKEN_KEY);
  }
  return null;
}

export function setSelfHostedToken(token: string | null): void {
  if (typeof window !== 'undefined' && window.localStorage) {
    if (token) {
      window.localStorage.setItem(SELF_HOSTED_TOKEN_KEY, token);
    } else {
      window.localStorage.removeItem(SELF_HOSTED_TOKEN_KEY);
    }
  }
}

export function getSelfHostedUser(): SelfHostedUser | null {
  if (typeof window !== 'undefined' && window.localStorage) {
    const raw = window.localStorage.getItem(SELF_HOSTED_USER_KEY);
    if (raw) {
      try {
        return JSON.parse(raw) as SelfHostedUser;
      } catch {
        return null;
      }
    }
  }
  return null;
}

export function setSelfHostedUser(user: SelfHostedUser | null): void {
  if (typeof window !== 'undefined' && window.localStorage) {
    if (user) {
      window.localStorage.setItem(SELF_HOSTED_USER_KEY, JSON.stringify(user));
    } else {
      window.localStorage.removeItem(SELF_HOSTED_USER_KEY);
    }
  }
}

export function clearSelfHostedAuth(): void {
  setSelfHostedToken(null);
  setSelfHostedUser(null);
}
