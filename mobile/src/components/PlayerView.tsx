import { useRouter } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import type { GameRow, HotColdHistory, Stats } from '@/api/types';
import { Badge, Card, ListItem, Robe, Row, Section, Stat, T } from '@/components/ui';
import { formatDay, t } from '@/i18n';
import { colors, radius, space, type, verdictColors } from '@/theme';

/** Statistiques et historiques d'un joueur : partagé par « Profil » et la fiche d'un autre joueur. */
export function PlayerView({ stats, games, hotcold, self }: {
  stats: Stats; games: GameRow[]; hotcold: HotColdHistory[]; self: boolean;
}) {
  const router = useRouter();
  return (
    <>
      <Card>
        <Row>
          <Stat value={stats.played} label={t.played} />
          <Stat value={`${stats.rate} %`} label={t.wins} />
          <Stat value={stats.avg} label={t.avg} />
        </Row>
      </Card>

      {stats.regions.length > 0 && (
        <Section title={t.byRegion}>
          <Card style={{ gap: space.s }}>
            {stats.regions.slice(0, 8).map((r) => (
              <View key={r.name} style={{ gap: 4 }}>
                <Row style={{ justifyContent: 'space-between' }}>
                  <Text style={type.small}>{r.name}</Text>
                  <Text style={type.caption}>{r.won}/{r.played}</Text>
                </Row>
                <View style={styles.track}><View style={[styles.fill, { width: `${r.rate}%` }]} /></View>
              </View>
            ))}
          </Card>
        </Section>
      )}

      <Section title={`${t.history} · ${t.blindtest}`}>
        {games.length ? (
          <View style={styles.list}>
            {games.map((g) => (
              <ListItem key={g.id}
                title={g.wine?.name ?? t.inProgress}
                subtitle={`${g.mode_label} · ${new Date(g.created_at).toLocaleDateString()}`}
                left={<Robe color={g.wine?.color} />}
                right={<Badge label={g.status === 'playing' ? g.status_label : `${g.score} ${t.points}`}
                  tone={g.status === 'won' ? verdictColors.hit : g.status === 'playing' ? verdictColors.close : verdictColors.miss} />}
                onPress={() => router.push(`/game/${g.id}`)} />
            ))}
          </View>
        ) : <T.Small>{t.noGames}</T.Small>}
      </Section>

      <Section title={t.hotcoldHistory}>
        {hotcold.length ? (
          <View style={styles.list}>
            {hotcold.map((h) => (
              <ListItem key={h.day}
                title={h.wine?.name ?? '—'}
                subtitle={`${formatDay(h.day)} · ${t.guesses(h.guesses)}`}
                left={<Robe color={h.wine?.color} />}
                right={<Badge label={h.outcome === 'won' ? `${h.score} ${t.points}` : h.outcome_label}
                  tone={h.outcome === 'won' ? verdictColors.hit : verdictColors.miss} />}
                onPress={h.wine ? () => router.push(`/wine/${h.wine!.slug}`) : undefined} />
            ))}
          </View>
        ) : <T.Small>{self ? t.noGames : '—'}</T.Small>}
      </Section>
    </>
  );
}

const styles = StyleSheet.create({
  list: { borderRadius: radius.l, overflow: 'hidden', borderWidth: 1, borderColor: colors.rule },
  track: { height: 6, borderRadius: 3, backgroundColor: colors.chalk, overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3, backgroundColor: colors.olive },
});
