/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { getSelfHostedBaseUrl, getSelfHostedToken } from '../config/selfHosted';

export type LogLevel = 'INFO' | 'WARN' | 'ERROR' | 'DEBUG';

export function reportLog(level: LogLevel, message: string, clientInfo?: string): void {
  try {
    const token = getSelfHostedToken();
    if (!token) return;

    const baseUrl = getSelfHostedBaseUrl();
    const payload = {
      level: level.toUpperCase(),
      message,
      client_info: clientInfo || (typeof navigator !== 'undefined' ? navigator.userAgent : 'Desktop Win7'),
    };

    fetch(`${baseUrl}/api/logs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    }).catch(() => {
      // Silently ignore reporting errors so main app is never blocked
    });
  } catch {
    // Silently ignore
  }
}
