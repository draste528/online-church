import { API_URL, AUTH_MOCK } from '../config';
import type { TokenReply } from './types';

export class AuthError extends Error {
  constructor(public status: number, public fields: Record<string, string> = {}) { super(`Auth HTTP ${status}`); }
}
export async function checked<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const fields: Record<string, string> = {};
    try {
      const body = await response.json();
      if (Array.isArray(body.detail)) for (const item of body.detail) {
        const field = item.loc?.at(-1);
        if (typeof field === 'string') fields[field] = 'invalid';
      }
    } catch { /* Non-JSON errors use a translated generic message. */ }
    throw new AuthError(response.status, fields);
  }
  return response.status === 204 ? undefined as T : response.json();
}
export async function authRequest(path: string, init: RequestInit = {}): Promise<Response> {
  const options = { ...init, credentials: 'include' as const };
  if (AUTH_MOCK) return (await import('../data/authMock')).authMock(path, options);
  return fetch(`${API_URL}/api/v1/auth${path}`, options);
}
export const jsonBody = (value: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) });

// Contains callbacks only; the access token itself belongs to AuthProvider state.
interface Bridge {
  token(): string | null;
  accept(reply: TokenReply): void;
  expire(): void;
}
let bridge: Bridge | null = null;
let refreshPromise: Promise<TokenReply> | null = null;
let generation = 0;
export function connectAuth(value: Bridge): () => void {
  bridge = value;
  return () => { if (bridge === value) bridge = null; };
}
export function invalidateAuth(): void { generation++; }
export async function settleRefresh(): Promise<void> { await refreshPromise?.catch(() => undefined); }
export function refreshAuth(): Promise<TokenReply> {
  if (!refreshPromise) {
    const version = generation;
    refreshPromise = authRequest('/refresh', { method: 'POST' }).then(checked<TokenReply>).then(reply => {
      if (version !== generation) throw new AuthError(401);
      bridge?.accept(reply);
      return reply;
    }).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}
export async function authenticatedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!path.startsWith('/api/v1/') || path.includes('\\')) throw new Error('Expected an internal API path');
  const owner = bridge;
  const version = generation;
  const token = owner?.token();
  const request = () => {
    const headers = new Headers(init.headers);
    const current = owner?.token();
    if (current) headers.set('Authorization', `Bearer ${current}`);
    if (path.startsWith('/api/v1/auth/')) return authRequest(path.slice('/api/v1/auth'.length), { ...init, headers });
    return fetch(`${API_URL}${path}`, { ...init, headers });
  };
  let response = await request();
  if (version !== generation || owner !== bridge) throw new AuthError(401);
  if (response.status !== 401) return response;
  try {
    // A different request may already have refreshed while this 401 was in flight.
    if (!owner?.token() || owner.token() === token) await refreshAuth();
  } catch (error) {
    if (error instanceof AuthError && error.status === 401 && version === generation) owner?.expire();
    throw error;
  }
  if (version !== generation || owner !== bridge) throw new AuthError(401);
  response = await request();
  if (version !== generation || owner !== bridge) throw new AuthError(401);
  if (response.status === 401) owner?.expire();
  return response;
}
