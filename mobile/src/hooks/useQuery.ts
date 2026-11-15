import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';

import { useAuth } from '@/auth';

/**
 * Charge une ressource quand l'écran prend le focus (et après connexion ou déconnexion).
 * `fetcher` doit être stable (fonction de `api` ou useCallback).
 * `refresh` sert au tirer-pour-actualiser ; `setData` aux réponses des actions (essai, abandon).
 */
export function useQuery<T>(fetcher: () => Promise<T>) {
  const { version } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const seq = useRef(0);

  const load = useCallback(async (mode: 'focus' | 'refresh' = 'focus') => {
    const id = ++seq.current;
    if (mode === 'refresh') setRefreshing(true);
    try {
      const result = await fetcher();
      if (id === seq.current) {
        setData(result);
        setError(null);
      }
    } catch (e) {
      if (id === seq.current) setError(e);
    } finally {
      if (id === seq.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
    // `version` change à la connexion ou déconnexion : les données du joueur sont rechargées.
  }, [version, fetcher]); // eslint-disable-line react-hooks/exhaustive-deps

  useFocusEffect(useCallback(() => { load(); }, [load]));

  return { data, setData, error, loading, refreshing, refresh: () => load('refresh'), reload: () => load() };
}
