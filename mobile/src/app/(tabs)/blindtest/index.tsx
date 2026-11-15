import { Stack, useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert, View } from 'react-native';

import { api } from '@/api/client';
import { Badge, Button, Card, ErrorView, ListItem, Loading, Robe, Row, Screen, Section, T, errorMessage } from '@/components/ui';
import { useQuery } from '@/hooks/useQuery';
import { t } from '@/i18n';
import { tabRootOptions } from '@/navigation';
import { colors, radius, verdictColors } from '@/theme';

const statusTone = (s: string) => (s === 'won' ? verdictColors.hit : s === 'playing' ? verdictColors.close : verdictColors.miss);

export default function BlindTestHome() {
  const router = useRouter();
  const games = useQuery(api.myGames);
  const [busy, setBusy] = useState<string | null>(null);

  const start = async (mode: 'daily' | 'free') => {
    setBusy(mode);
    try {
      const g = await api.newGame(mode);
      router.push(`/game/${g.id}`);
    } catch (e) {
      Alert.alert(t.error, errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const options = { ...tabRootOptions, title: t.blindtest };
  return (
    <Screen refreshing={games.refreshing} onRefresh={games.refresh}>
      <Stack.Screen options={options} />
      <Card>
        <T.Body>{t.blindtestPitch}</T.Body>
        <Row>
          <Button title={t.daily} icon="calendar"
            style={{ flex: 1 }} loading={busy === 'daily'} onPress={() => start('daily')} />
          <Button title={t.freeGame} icon="shuffle" variant="secondary" style={{ flex: 1 }}
            loading={busy === 'free'} onPress={() => start('free')} />
        </Row>
      </Card>

      <Section title={t.myGames}>
        {games.loading && !games.data ? <Loading /> : games.error && !games.data ? (
          <ErrorView error={games.error} onRetry={games.reload} />
        ) : games.data?.results.length ? (
          <View style={{ borderRadius: radius.l, overflow: 'hidden', borderWidth: 1, borderColor: colors.rule }}>
            {games.data.results.map((g) => (
              <ListItem key={g.id}
                title={g.wine?.name ?? t.inProgress}
                subtitle={`${g.mode_label} · ${new Date(g.created_at).toLocaleDateString()}`}
                left={<Robe color={g.wine?.color} />}
                right={<Badge label={g.status === 'playing' ? g.status_label : `${g.score} ${t.points}`} tone={statusTone(g.status)} />}
                onPress={() => router.push(`/game/${g.id}`)} />
            ))}
          </View>
        ) : <T.Small>{t.noGames}</T.Small>}
      </Section>
    </Screen>
  );
}
