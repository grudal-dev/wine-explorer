import * as Haptics from 'expo-haptics';
import { Stack, useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';

import { api } from '@/api/client';
import type { HotColdBoard, HotColdRow } from '@/api/types';
import { useAuth } from '@/auth';
import { GuessInput } from '@/components/GuessInput';
import { Badge, Button, Card, ErrorView, Loading, Notice, Robe, Row, Screen, Section, T, errorMessage } from '@/components/ui';
import { useQuery } from '@/hooks/useQuery';
import { t } from '@/i18n';
import { tabRootOptions } from '@/navigation';
import { shareHotcold } from '@/share';
import { colors, fonts, radius, space, type } from '@/theme';

/** Couleur d'une température : du bleu glacial au grenat brûlant. */
function heat(row: HotColdRow): string {
  if (row.found) return colors.olive;
  if (row.rank <= 20) return colors.garnet;
  if (row.rank <= 100) return '#B4452F';
  if (row.temperature > 0) return colors.ochre;
  return colors.slate;
}

function TempRow({ row, highlight }: { row: HotColdRow; highlight?: boolean }) {
  const c = heat(row);
  return (
    <View style={[styles.row, highlight && { backgroundColor: colors.garnetWash }]}>
      <Text style={styles.emoji}>{row.emoji}</Text>
      <View style={{ flex: 1, gap: 4 }}>
        <Row style={{ justifyContent: 'space-between' }}>
          <Text style={[type.body, { fontFamily: fonts.sansMedium, flex: 1 }]} numberOfLines={1}>{row.label}</Text>
          <Text style={[styles.temp, { color: c }]}>{row.temperature.toFixed(1)}°</Text>
        </Row>
        <Row style={{ gap: space.s }}>
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${Math.max(row.gauge, row.temperature > 0 ? 3 : 0)}%`, backgroundColor: c }]} />
          </View>
          <Text style={[type.caption, { width: 92, textAlign: 'right' }]} numberOfLines={1}>
            {row.found ? row.band : row.rank <= 100 ? `${t.rank} ${row.rank}` : row.band}
          </Text>
        </Row>
        <Text style={type.caption}>{row.type_label}</Text>
      </View>
    </View>
  );
}

function Board({ rows, highlight }: { rows: HotColdRow[]; highlight?: number }) {
  return (
    <View style={styles.board}>
      {rows.map((r, i) => (
        <View key={r.id} style={i > 0 && styles.sep}><TempRow row={r} highlight={r.n !== undefined && r.n === highlight} /></View>
      ))}
    </View>
  );
}

export default function HotCold() {
  const router = useRouter();
  const { signedIn } = useAuth();
  const { data: board, setData, error, loading, refreshing, refresh, reload } = useQuery(api.hotcold);
  const [message, setMessage] = useState<string | null>(null);

  const play = async (q: string, choice: string) => {
    setMessage(null);
    try {
      const next = await api.hotcoldGuess(q, choice);
      setData(next);
      if (next.over === 'won') Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      else if (next.last && next.last.rank <= 20) Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
      else Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      return true;
    } catch (e) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      setMessage(errorMessage(e));
      return false;
    }
  };

  const act = async (fn: () => Promise<HotColdBoard>) => {
    setMessage(null);
    try { setData(await fn()); } catch (e) { setMessage(errorMessage(e)); }
  };

  const giveUp = () => Alert.alert(t.giveUp, t.giveUpConfirm, [
    { text: t.cancel, style: 'cancel' },
    { text: t.giveUp, style: 'destructive', onPress: () => act(api.hotcoldGiveUp) },
  ]);

  const options = { ...tabRootOptions, title: t.hotcold };
  if (loading && !board) return <><Stack.Screen options={options} /><Loading /></>;
  if (error && !board) return <><Stack.Screen options={options} /><ErrorView error={error} onRetry={reload} /></>;
  if (!board) return null;

  const over = !!board.over;
  const answerSlug = board.answer?.id.split(':')[1];

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <Stack.Screen options={options} />
      <Row style={{ justifyContent: 'space-between' }}>
        <Badge label={board.mode === 'daily' ? t.daily : t.freeGame}
          tone={board.mode === 'daily' ? { fg: colors.garnet, bg: colors.garnetWash } : { fg: colors.slate, bg: colors.slateWash }} />
        <T.Small>{t.guesses(board.count)}</T.Small>
      </Row>

      {over && board.answer && (
        <Card style={{ alignItems: 'center', backgroundColor: board.over === 'won' ? colors.oliveWash : colors.card }}>
          <T.Caption>{board.over === 'won' ? t.foundIn(board.count) : t.abandoned}</T.Caption>
          <Row><Robe color={board.answer.wine} size={18} /><T.Title>{board.answer.label}</T.Title></Row>
          {board.ranked ? <T.Small>{t.ranked} · {board.ranked.score} {t.points}</T.Small>
            : board.mode === 'daily' && !signedIn ? <T.Small>{t.signInToRank}</T.Small> : null}
          <Row style={{ alignSelf: 'stretch' }}>
            {answerSlug && <Button title={t.seeWine} icon="wine" variant="secondary" style={{ flex: 1 }}
              onPress={() => router.push(`/wine/${answerSlug}`)} />}
            <Button title={t.share} icon="share-outline" variant="secondary" style={{ flex: 1 }} onPress={() => shareHotcold(board)} />
          </Row>
          <Button title={t.newGame} icon="shuffle" style={{ alignSelf: 'stretch' }} onPress={() => act(() => api.hotcoldNew('free'))} />
          {board.mode === 'free' && (
            <Button title={t.backToDaily} variant="ghost" onPress={() => act(() => api.hotcoldNew('daily'))} />
          )}
        </Card>
      )}

      {!over && (
        <View style={{ gap: space.s }}>
          {board.count === 0 && <T.Small>{t.hotcoldIntro}</T.Small>}
          <GuessInput placeholder={t.hotcoldPlaceholder} suggest={api.suggestHot} onSubmit={play} />
          {message && <Notice text={message} tone="error" />}
          {board.last && (
            <Section title={t.last}>
              <View style={styles.board}><TempRow row={board.last} highlight /></View>
            </Section>
          )}
        </View>
      )}

      {board.rows.length > 0 && (
        <Section title={t.guesses(board.count)}>
          <Board rows={board.rows} highlight={board.last?.n} />
        </Section>
      )}

      {over && board.closest && (
        <Section title={t.closest}>
          <Board rows={board.closest} />
        </Section>
      )}

      {!over && (
        <Row>
          {board.mode === 'free'
            ? <Button title={t.backToDaily} variant="secondary" style={{ flex: 1 }} onPress={() => act(() => api.hotcoldNew('daily'))} />
            : <Button title={t.freeGame} icon="shuffle" variant="secondary" style={{ flex: 1 }} onPress={() => act(() => api.hotcoldNew('free'))} />}
          <Button title={t.giveUp} icon="flag-outline" variant="ghost" onPress={giveUp} />
        </Row>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  board: { backgroundColor: colors.card, borderRadius: radius.l, borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.rule, overflow: 'hidden' },
  sep: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.rule },
  row: { flexDirection: 'row', gap: space.m, padding: space.m, alignItems: 'center' },
  emoji: { fontSize: 24, width: 32, textAlign: 'center' },
  temp: { fontFamily: fonts.serifBold, fontSize: 18 },
  track: { flex: 1, height: 6, borderRadius: 3, backgroundColor: colors.chalk, overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3 },
});
