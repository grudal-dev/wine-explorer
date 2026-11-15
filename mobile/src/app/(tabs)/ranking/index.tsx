import { Stack, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { api } from '@/api/client';
import type { RankingRow } from '@/api/types';
import { useAuth } from '@/auth';
import { ErrorView, ListItem, Loading, Screen, Segmented, T } from '@/components/ui';
import { useQuery } from '@/hooks/useQuery';
import { t } from '@/i18n';
import { tabRootOptions } from '@/navigation';
import { colors, fonts, radius, space } from '@/theme';

type Game = 'total' | 'blindtest' | 'hotcold';
const MEDALS = ['🥇', '🥈', '🥉'];

function Rank({ i }: { i: number }) {
  return (
    <View style={styles.rank}>
      {i < 3 ? <Text style={{ fontSize: 20 }}>{MEDALS[i]}</Text>
        : <Text style={styles.rankText}>{i + 1}</Text>}
    </View>
  );
}

export default function Ranking() {
  const router = useRouter();
  const { user } = useAuth();
  const [game, setGame] = useState<Game>('total');
  const [period, setPeriod] = useState<'today' | 'all_time'>('today');
  const fetcher = useCallback(() => api.rankings(game), [game]);
  const { data, error, loading, refreshing, refresh, reload } = useQuery(fetcher);

  const rows: RankingRow[] = data?.game === game ? data[period] : [];
  const detail = (r: RankingRow) => {
    if (game === 'total') return `${t.blindtest} ${r.blindtest ?? 0} · ${t.hotcold} ${r.hotcold ?? 0}`;
    if (period === 'today') return r.result ? `${r.result}${r.guesses ? ` · ${t.guesses(r.guesses)}` : ''}` : '';
    return `${r.played} ${t.played} · ${r.wins} ✓`;
  };

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <Stack.Screen options={{ ...tabRootOptions, title: t.ranking }} />
      <Segmented value={game} onChange={setGame}
        options={[{ key: 'total', label: t.total }, { key: 'blindtest', label: t.blindtest }, { key: 'hotcold', label: t.hotcold }]} />
      <Segmented value={period} onChange={setPeriod}
        options={[{ key: 'today', label: t.todayTab }, { key: 'all_time', label: t.allTime }]} />

      {loading && !data ? <Loading /> : error && !data ? <ErrorView error={error} onRetry={reload} /> : rows.length ? (
        <View style={styles.list}>
          {rows.map((r, i) => (
            <ListItem key={r.username} left={<Rank i={i} />}
              title={r.username === user?.username ? `${r.username} ★` : r.username}
              subtitle={detail(r)}
              right={<Text style={styles.points}>{r.points}</Text>}
              onPress={() => router.push(`/player/${encodeURIComponent(r.username)}`)} />
          ))}
        </View>
      ) : <T.Small style={{ textAlign: 'center' }}>{t.nobodyYet}</T.Small>}
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { borderRadius: radius.l, overflow: 'hidden', borderWidth: 1, borderColor: colors.rule },
  rank: { width: 32, alignItems: 'center' },
  rankText: { fontFamily: fonts.serifBold, fontSize: 17, color: colors.ink2 },
  points: { fontFamily: fonts.serifBold, fontSize: 18, color: colors.garnet, marginRight: space.xs },
});
