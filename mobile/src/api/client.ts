/**
 * Client de l'API Django (/api/v1/).
 *
 * Adresse du serveur :
 *  - EXPO_PUBLIC_API_URL si elle est définie (production, ou serveur distant) ;
 *  - sinon, en développement, la machine qui fait tourner `npx expo start`, port 8000 :
 *    c'est le PC où tourne aussi `python manage.py runserver 0.0.0.0:8000`.
 */
import Constants from 'expo-constants';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';

import { lang } from '@/i18n';
import type {
  Game, GameRow, HotColdBoard, Me, Player, Rankings, Suggestion, Today, User, Wine, WineBrief,
} from './types';

function resolveBaseUrl(): string {
  const configured = process.env.EXPO_PUBLIC_API_URL;
  if (configured) return configured.replace(/\/+$/, '');
  const host = Constants.expoConfig?.hostUri?.split(':')[0];
  return `http://${host || 'localhost'}:8000/api/v1`;
}

export const API_URL = resolveBaseUrl();

const TOKEN_KEY = 'we.token';
const DEVICE_KEY = 'we.device';

let token: string | null = null;
let device: string | null = null;

/** Charge le jeton et l'identifiant d'appareil (créé au premier lancement). */
export async function bootstrap(): Promise<string | null> {
  token = await SecureStore.getItemAsync(TOKEN_KEY);
  device = await SecureStore.getItemAsync(DEVICE_KEY);
  if (!device) {
    device = Crypto.randomUUID();
    await SecureStore.setItemAsync(DEVICE_KEY, device);
  }
  return token;
}

export async function setToken(value: string | null) {
  token = value;
  if (value) await SecureStore.setItemAsync(TOKEN_KEY, value);
  else await SecureStore.deleteItemAsync(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  fields: Record<string, string[]>;
  constructor(message: string, status: number, fields: Record<string, string[]> = {}) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

export class NetworkError extends Error {}

type Method = 'GET' | 'POST' | 'DELETE';

async function request<T>(method: Method, path: string, body?: unknown, query?: Record<string, string>): Promise<T> {
  const qs = query ? `?${new URLSearchParams(query).toString()}` : '';
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Accept-Language': lang,
  };
  if (device) headers['X-Device-Id'] = device;
  if (token) headers.Authorization = `Token ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}${qs}`, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal,
    });
  } catch {
    throw new NetworkError(API_URL);
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401 && token) {
    await setToken(null); // jeton révoqué : on repasse en invité
    onSignedOut?.();
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.detail || `HTTP ${res.status}`, res.status, data.errors || {});
  return data as T;
}

let onSignedOut: (() => void) | undefined;
export const setSignedOutHandler = (fn: () => void) => { onSignedOut = fn; };

const get = <T>(path: string, query?: Record<string, string>) => request<T>('GET', path, undefined, query);
const post = <T>(path: string, body: unknown = {}) => request<T>('POST', path, body);

export const api = {
  signup: (data: { username: string; email: string; password: string; adult: boolean; newsletter: boolean }) =>
    post<{ token: string; user: User }>('/auth/signup/', data),
  login: (username: string, password: string) => post<{ token: string; user: User }>('/auth/login/', { username, password }),
  logout: () => post<void>('/auth/logout/'),
  me: () => get<Me>('/me/'),
  deleteAccount: (password: string) => request<void>('DELETE', '/me/', { password }),

  today: () => get<Today>('/today/'),

  myGames: () => get<{ results: GameRow[] }>('/blindtest/games/'),
  newGame: (mode: 'daily' | 'free', color = '') => post<Game>('/blindtest/games/', { mode, color }),
  game: (id: string) => get<Game>(`/blindtest/games/${id}/`),
  guess: (id: string, q: string, choice = '') => post<Game>(`/blindtest/games/${id}/guess/`, { q, choice }),
  giveUp: (id: string) => post<Game>(`/blindtest/games/${id}/give-up/`),
  suggestBlind: async (q: string): Promise<Suggestion[]> => {
    const r = await get<{ results: { kind: string; pk: number; label: string; kind_label: string }[] }>(
      '/blindtest/suggest/', { q });
    return r.results
      .filter((x) => x.kind !== 'color' && x.kind !== 'style')
      .map((x) => ({ key: `${x.kind}:${x.pk}`, label: x.label, hint: x.kind_label, choice: `${x.kind}:${x.pk}` }));
  },

  hotcold: () => get<HotColdBoard>('/hotcold/'),
  hotcoldNew: (mode: 'daily' | 'free') => post<HotColdBoard>('/hotcold/new/', { mode }),
  hotcoldGuess: (q: string, choice = '') => post<HotColdBoard>('/hotcold/guess/', { q, choice }),
  hotcoldGiveUp: () => post<HotColdBoard>('/hotcold/give-up/'),
  suggestHot: async (q: string): Promise<Suggestion[]> => {
    const r = await get<{ results: { id: string; label: string; type_label: string }[] }>('/hotcold/suggest/', { q });
    return r.results.map((x) => ({ key: x.id, label: x.label, hint: x.type_label, choice: x.id }));
  },

  rankings: (game: string) => get<Rankings>('/rankings/', { game }),
  player: (username: string) => get<Player>(`/players/${encodeURIComponent(username)}/`),
  wine: (slug: string) => get<Wine>(`/wines/${slug}/`),
  wines: (q: string) => get<{ results: WineBrief[] }>('/wines/', { q }),
};
