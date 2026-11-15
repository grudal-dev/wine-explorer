import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api, bootstrap, setSignedOutHandler, setToken } from '@/api/client';
import type { User } from '@/api/types';

type AuthState = {
  ready: boolean;
  signedIn: boolean;
  user: User | null;
  /** Incrémenté à chaque connexion ou déconnexion : les écrans rechargent leurs données. */
  version: number;
  signIn: (username: string, password: string) => Promise<void>;
  signUp: (data: Parameters<typeof api.signup>[0]) => Promise<void>;
  signOut: () => Promise<void>;
  deleteAccount: (password: string) => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [version, setVersion] = useState(0);

  const reset = useCallback(() => {
    setSignedIn(false);
    setUser(null);
    setVersion((v) => v + 1);
  }, []);

  useEffect(() => {
    setSignedOutHandler(reset);
    bootstrap()
      .then(async (token) => {
        if (!token) return;
        setSignedIn(true);
        try {
          setUser((await api.me()).user);
        } catch {
          // hors ligne : on garde le jeton, l'écran de profil réessaiera
        }
      })
      .finally(() => setReady(true));
  }, [reset]);

  const accept = useCallback(async ({ token, user: u }: { token: string; user: User }) => {
    await setToken(token);
    setUser(u);
    setSignedIn(true);
    setVersion((v) => v + 1);
  }, []);

  const value = useMemo<AuthState>(() => ({
    ready, signedIn, user, version,
    signIn: async (username, password) => accept(await api.login(username, password)),
    signUp: async (data) => accept(await api.signup(data)),
    signOut: async () => {
      await api.logout().catch(() => undefined);
      await setToken(null);
      reset();
    },
    deleteAccount: async (password) => {
      await api.deleteAccount(password);
      await setToken(null);
      reset();
    },
  }), [ready, signedIn, user, version, accept, reset]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth hors de AuthProvider');
  return ctx;
}
