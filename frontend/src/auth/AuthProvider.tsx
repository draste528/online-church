import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthError, authRequest, authenticatedFetch, checked, connectAuth, invalidateAuth, jsonBody, refreshAuth, settleRefresh } from './client';
import type { Credentials, Registration, TokenReply, User } from './types';

interface AuthValue {
  user: User | null;
  accessToken: string | null;
  status: 'loading' | 'guest' | 'authenticated';
  login(data: Credentials): Promise<void>;
  register(data: Registration): Promise<void>;
  logout(): Promise<void>;
  reloadUser(): Promise<User>;
}
const Context = createContext<AuthValue | null>(null);
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<{ user: User | null; accessToken: string | null; status: AuthValue['status'] }>({ user: null, accessToken: null, status: 'loading' });
  const current = useRef(session);
  const startup = useRef<Promise<void>>();
  const navigate = useNavigate();
  const update = (value: typeof session) => { current.current = value; setSession(value); };
  const clear = () => { invalidateAuth(); update({ user: null, accessToken: null, status: 'guest' }); };
  const reloadUser = async () => {
    const user = await checked<User>(await authenticatedFetch('/api/v1/auth/me'));
    if (!current.current.accessToken) throw new AuthError(401);
    update({ ...current.current, user, status: 'authenticated' });
    return user;
  };
  useEffect(() => {
    const disconnect = connectAuth({
      token: () => current.current.accessToken,
      accept: reply => update({ ...current.current, accessToken: reply.access_token }),
      expire: () => {
        clear();
        const next = window.location.pathname + window.location.search + window.location.hash;
        navigate(`/login?next=${encodeURIComponent(next)}`, { replace: true });
      },
    });
    // StrictMode remounts effects: retain the one startup operation.
    startup.current ??= refreshAuth().then(async () => { await reloadUser(); }).catch(() => clear());
    return disconnect;
  }, []); // The bridge deliberately reads the latest state through current.
  const login = async (data: Credentials) => {
    await startup.current;
    const reply = await checked<TokenReply>(await authRequest('/login', jsonBody(data)));
    update({ user: null, accessToken: reply.access_token, status: 'loading' });
    try { await reloadUser(); } catch (error) { clear(); throw error; }
  };
  const register = async (data: Registration) => {
    await checked<User>(await authRequest('/register', jsonBody(data)));
    await login({ email: data.email, password: data.password });
  };
  const logout = async () => {
    clear();
    try { await settleRefresh(); await checked<void>(await authRequest('/logout', { method: 'POST' })); }
    finally { clear(); }
  };
  return <Context.Provider value={{ ...session, login, register, logout, reloadUser }}>{children}</Context.Provider>;
}
export function useAuth(): AuthValue {
  const value = useContext(Context);
  if (!value) throw new Error('useAuth requires AuthProvider');
  return value;
}
