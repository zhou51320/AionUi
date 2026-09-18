import type { ConfigKey, ConfigKeyMap } from './configKeys';
import { getSelfHostedBaseUrl, getSelfHostedToken } from './selfHosted';

type Subscriber = (value: unknown) => void;

declare global {
  interface Window {
    __backendPort?: number;
  }
}

function getBaseUrl(): string {
  // WebUI browser mode: no preload, fetch same-origin so web-host's
  // static-server reverse-proxies /api/* to the backend.
  if (typeof window !== 'undefined' && typeof document !== 'undefined' && !(window as Window).__backendPort) {
    return '';
  }
  const port = typeof window !== 'undefined' ? (window as Window).__backendPort || 13400 : 13400;
  return `http://127.0.0.1:${port}`;
}

async function fetchJson<T>(method: string, path: string, body?: unknown): Promise<T> {
  const url = `${getBaseUrl()}${path}`;
  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`ConfigService ${method} ${path} failed (${response.status}): ${errorBody}`);
  }
  const contentType = response.headers.get('Content-Type');
  if (!contentType?.includes('application/json')) {
    return undefined as T;
  }
  const json = await response.json();
  if (json && typeof json === 'object' && 'data' in json) {
    return json.data as T;
  }
  return json as T;
}

class ConfigServiceImpl {
  private cache = new Map<string, unknown>();
  private subscribers = new Map<string, Set<Subscriber>>();
  private initialized = false;
  private initPromise: Promise<void> | null = null;

  // Idempotent: concurrent callers share the same in-flight promise, and a
  // resolved init returns immediately. Modules that need persisted settings on
  // module load (theme/language) await whenReady() before reading.
  initialize(): Promise<void> {
    if (this.initPromise) return this.initPromise;
    this.initPromise = (async () => {
      const data = await fetchJson<Record<string, unknown>>('GET', '/api/settings/client');
      this.cache.clear();
      if (data) {
        for (const [key, value] of Object.entries(data)) {
          this.cache.set(key, value);
        }
      }
      this.initialized = true;
      void this.syncFromSelfHosted();
    })();
    this.initPromise.catch(() => {
      // Allow a future caller to retry after a transient failure
      this.initPromise = null;
    });
    return this.initPromise;
  }

  async syncFromSelfHosted(): Promise<boolean> {
    const token = getSelfHostedToken();
    if (!token) return false;
    try {
      const baseUrl = getSelfHostedBaseUrl();
      const res = await fetch(`${baseUrl}/api/config`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.ok) {
        const json = await res.json();
        if (json.code === 0 && json.data) {
          const cfg = json.data;
          if (cfg.model_name) {
            this.cache.set('synced_model_name', cfg.model_name);
          }
          if (cfg.base_url) {
            this.cache.set('synced_base_url', cfg.base_url);
          }
          if (cfg.api_key) {
            this.cache.set('synced_api_key', cfg.api_key);
          }
          if (cfg.extra_config && typeof cfg.extra_config === 'object') {
            for (const [k, v] of Object.entries(cfg.extra_config)) {
              this.cache.set(`synced_${k}`, v);
            }
          }

          // Synchronize provider and models into AionCore backend (/api/providers)
          const providerId = 'self-hosted-provider';
          const platform = cfg.platform || 'openai';
          const providerName = cfg.provider_name || '自托管模型服务';
          const models: string[] = Array.isArray(cfg.models) && cfg.models.length > 0
            ? cfg.models
            : (cfg.model_name ? [cfg.model_name] : []);

          const customConfigs: Record<string, unknown> = {};
          const modelProtocols: Record<string, string> = {};
          for (const m of models) {
            customConfigs[m] = {
              image_input: cfg.image_input || 'auto',
              openai_api_mode: cfg.openai_api_mode || 'auto',
              thought_level: cfg.thought_level || 'auto',
              context_limit: cfg.context_limit ? Number(cfg.context_limit) : undefined,
            };
            if (cfg.model_protocol) {
              modelProtocols[m] = cfg.model_protocol;
            }
          }

          const providerPayload = {
            id: providerId,
            platform,
            name: providerName,
            base_url: cfg.base_url || '',
            api_key: cfg.api_key || '',
            models,
            enabled: true,
            context_limit: cfg.context_limit ? Number(cfg.context_limit) : undefined,
            model_custom_configs: customConfigs,
            model_protocols: modelProtocols,
          };

          try {
            const existingList = await fetchJson<Array<{ id: string }>>('GET', '/api/providers');
            const exists = Array.isArray(existingList) && existingList.some((p) => p.id === providerId);
            if (exists) {
              await fetchJson('PUT', `/api/providers/${providerId}`, providerPayload);
            } else {
              await fetchJson('POST', '/api/providers', providerPayload);
            }
            return true;
          } catch (providerErr) {
            console.warn('ConfigService: failed to persist self-hosted provider to /api/providers:', providerErr);
          }
        }
      }
    } catch (err) {
      console.warn('ConfigService: failed to sync from self-hosted backend:', err);
    }
    return false;
  }

  whenReady(): Promise<void> {
    return this.initialize();
  }

  get<K extends ConfigKey>(key: K): ConfigKeyMap[K] | undefined {
    return this.cache.get(key) as ConfigKeyMap[K] | undefined;
  }

  async set<K extends ConfigKey>(key: K, value: ConfigKeyMap[K]): Promise<void> {
    this.cache.set(key, value);
    this.notify(key, value);
    await fetchJson<void>('PUT', '/api/settings/client', { [key]: value });
  }

  setLocal<K extends ConfigKey>(key: K, value: ConfigKeyMap[K]): void {
    this.cache.set(key, value);
    this.notify(key, value);
  }

  async remove(key: ConfigKey): Promise<void> {
    this.cache.delete(key);
    this.notify(key, undefined);
    await fetchJson<void>('PUT', '/api/settings/client', { [key]: null });
  }

  async setBatch(entries: Partial<{ [K in ConfigKey]: ConfigKeyMap[K] }>): Promise<void> {
    for (const [key, value] of Object.entries(entries)) {
      this.cache.set(key, value);
      this.notify(key as ConfigKey, value);
    }
    await fetchJson<void>('PUT', '/api/settings/client', entries);
  }

  subscribe(key: ConfigKey, callback: Subscriber): () => void {
    if (!this.subscribers.has(key)) {
      this.subscribers.set(key, new Set());
    }
    this.subscribers.get(key)!.add(callback);
    return () => {
      this.subscribers.get(key)?.delete(callback);
    };
  }

  isInitialized(): boolean {
    return this.initialized;
  }

  reset(): void {
    this.cache.clear();
    this.subscribers.clear();
    this.initialized = false;
    this.initPromise = null;
  }

  private notify(key: ConfigKey, value: unknown): void {
    const subs = this.subscribers.get(key);
    if (subs) {
      for (const cb of subs) {
        cb(value);
      }
    }
  }
}

export const configService = new ConfigServiceImpl();
