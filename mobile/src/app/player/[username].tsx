import { Stack, useLocalSearchParams } from 'expo-router';
import { useCallback } from 'react';

import { api } from '@/api/client';
import { PlayerView } from '@/components/PlayerView';
import { ErrorView, Loading, Screen } from '@/components/ui';
import { useQuery } from '@/hooks/useQuery';

export default function PlayerScreen() {
  const { username } = useLocalSearchParams<{ username: string }>();
  const fetcher = useCallback(() => api.player(username), [username]);
  const { data, error, loading, refreshing, refresh, reload } = useQuery(fetcher);

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorView error={error} onRetry={reload} />;
  if (!data) return null;
  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <Stack.Screen options={{ title: data.username }} />
      <PlayerView stats={data.stats} games={data.games} hotcold={data.hotcold} self={data.is_self} />
    </Screen>
  );
}
