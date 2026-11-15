import Ionicons from '@expo/vector-icons/Ionicons';
import * as Haptics from 'expo-haptics';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';

import { api } from '@/api/client';
import type { Game, Guess } from '@/api/types';
import { GuessInput } from '@/components/GuessInput';
import {
  Badge, Button, Card, Chip, ErrorView, Loading, Meter, Notice, Robe, Row, Screen, Section, T, errorMessage,
} from '@/components/ui';
import { useQuery } from '@/hooks/useQuery';
import { t } from '@/i18n';
import { shareBlindtest } from '@/share';
import { colors, fonts, radius, space, type, verdictColors } from '@/theme';

const HAPTIC: Record<Guess['verdict'], () => void> = {
  hit: () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success),
  close: () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning),
  miss: () => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light),
  info: () => Haptics.selectionAsync(),
};

function Slots({ game }: { game: Game }) {
  return (
    <View style={styles.slots}>
      {game.sheet.slots.map((s, i) => (
        <View key={s.key} style={[styles.slot, i > 0 && styles.slotBorder]}>
          <Ionicons name={s.found ? 'checkmark-circle' : game.is_over ? 'close-circle' : 'ellipse-outline'} size={20}
            color={s.found ? colors.olive : game.is_over ? colors.garnet : colors.rule} />
          <Text style={[type.small, { width: 96 }]}>{s.label}</Text>
          <Text style={[type.body, { flex: 1, fontFamily: s.answer ? fonts.serifBold : fonts.sans,
            color: s.answer ? colors.ink : colors.ink3 }]} numberOfLines={1}>
            {s.answer ?? '? ? ?'}
          </Text>
        </View>
      ))}
    </View>
  );
}

function GuessRow({ g }: { g: Guess }) {
  const c = verdictColors[g.verdict];
  return (
    <View style={[styles.guess, { borderLeftColor: c.fg }]}>
      <Row style={{ justifyContent: 'space-between' }}>
        <Text style={[type.body, { fontFamily: fonts.sansBold, flex: 1 }]} numberOfLines={1}>{g.label}</Text>
        <Badge label={g.verdict_label} verdict={g.verdict} />
      </Row>
      {g.feedback ? <T.Small>{g.feedback}</T.Small> : null}
    </View>
  );
}

function Result({ game, onNew }: { game: Game; onNew: () => void }) {
  const router = useRouter();
  const title = game.status === 'won' ? t.won : game.status === 'lost' ? t.lost : t.abandoned;
  return (
    <Card style={{ alignItems: 'center', backgroundColor: game.status === 'won' ? colors.oliveWash : colors.card }}>
      <T.Caption>{game.is_owner ? title : game.player ?? ''}</T.Caption>
      <Text style={[type.display, { fontSize: 44, lineHeight: 50 }]}>{game.score}<Text style={type.heading}> {t.points}</Text></Text>
      {game.wine && (
        <Button variant="secondary" title={game.wine.name} icon="wine" style={{ alignSelf: 'stretch' }}
          onPress={() => router.push(`/wine/${game.wine!.slug}`)} />
      )}
      {game.is_owner && (
        <Row style={{ alignSelf: 'stretch' }}>
          <Button title={t.share} icon="share-outline" variant="secondary" style={{ flex: 1 }} onPress={() => shareBlindtest(game)} />
          <Button title={t.newGame} icon="shuffle" style={{ flex: 1 }} onPress={onNew} />
        </Row>
      )}
    </Card>
  );
}

export default function GameScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const fetchGame = useCallback(() => api.game(id), [id]);
  const { data: game, setData, error, loading, refreshing, refresh, reload } = useQuery(fetchGame);
  const [message, setMessage] = useState<string | null>(null);

  const play = async (q: string, choice: string) => {
    setMessage(null);
    try {
      const next = await api.guess(id, q, choice);
      const last = next.guesses[next.guesses.length - 1];
      if (last) HAPTIC[last.verdict]();
      if (next.status === 'won') Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setData(next);
      return true;
    } catch (e) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      setMessage(errorMessage(e));
      return false;
    }
  };

  const giveUp = () => Alert.alert(t.giveUp, t.giveUpConfirm, [
    { text: t.cancel, style: 'cancel' },
    { text: t.giveUp, style: 'destructive', onPress: async () => {
      try { setData(await api.giveUp(id)); } catch (e) { setMessage(errorMessage(e)); }
    } },
  ]);

  const newGame = async () => {
    try {
      const g = await api.newGame('free');
      router.replace(`/game/${g.id}`);
    } catch (e) {
      setMessage(errorMessage(e));
    }
  };

  if (loading && !game) return <Loading />;
  if (error && !game) return <ErrorView error={error} onRetry={reload} />;
  if (!game) return null;

  const { sheet } = game;
  const playing = game.is_owner && !game.is_over;
  const lastGuess = game.guesses[game.guesses.length - 1];

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <Stack.Screen options={{ title: game.mode_label }} />

      <Card>
        <Row style={{ justifyContent: 'space-between' }}>
          <Row style={{ gap: space.m }}>
            <Robe color={sheet.color} size={40} />
            <View>
              <T.Title>{sheet.color_label}</T.Title>
              <T.Small>{sheet.style}</T.Small>
            </View>
          </Row>
          {!game.is_over && (
            <View style={styles.attempts}>
              <Text style={type.number}>{game.attempts_left}</Text>
              <T.Caption>/ {game.max_attempts}</T.Caption>
            </View>
          )}
        </Row>
        <Slots game={game} />
      </Card>

      {game.is_over && <Result game={game} onNew={newGame} />}

      {playing && (
        <View style={{ gap: space.s }}>
          <GuessInput placeholder={t.guessPlaceholder} suggest={api.suggestBlind} onSubmit={play} />
          <T.Small style={{ paddingHorizontal: 2 }}>{t.attemptsLeft(game.attempts_left)}</T.Small>
          {message && <Notice text={message} tone="error" />}
          {!message && lastGuess && <GuessRow g={lastGuess} />}
        </View>
      )}

      <Section title={t.nose}>
        <View style={styles.wrap}>
          {sheet.aromas.map((a) => <Chip key={a.name} label={a.name} hue={a.hue} intensity={a.intensity} />)}
        </View>
        {sheet.aromas_hidden > 0 && !game.is_over && <T.Small>{t.moreAromas(sheet.aromas_hidden)}</T.Small>}
      </Section>

      <Section title={t.structure}>
        <Card style={{ gap: space.s }}>
          {sheet.structure.map((s) => <Meter key={s.label} label={s.label} value={s.value} />)}
        </Card>
      </Section>

      {(sheet.clues.length > 0 || sheet.next_clue) && (
        <Section title={t.clues}>
          {sheet.clues.map((c) => (
            <Card key={c.key} tone="wash" style={{ gap: 4 }}>
              <T.Caption>{c.title}</T.Caption>
              <T.Body>{c.body}</T.Body>
            </Card>
          ))}
          {sheet.next_clue && !game.is_over && (
            <Row style={styles.nextClue}>
              <Ionicons name="lock-closed-outline" size={14} color={colors.ink3} />
              <T.Small>{t.nextClue} : {sheet.next_clue}</T.Small>
            </Row>
          )}
        </Section>
      )}

      {game.guesses.length > 0 && (
        <Section title={t.yourGuesses}>
          {[...game.guesses].reverse().map((g, i) => <GuessRow key={`${g.label}-${i}`} g={g} />)}
        </Section>
      )}

      {game.is_over && sheet.minor_grapes.length > 0 && (
        <T.Small>{t.grapes} : {sheet.minor_grapes.join(', ')}</T.Small>
      )}

      {playing && <Button title={t.giveUp} variant="ghost" icon="flag-outline" onPress={giveUp} />}
    </Screen>
  );
}

const styles = StyleSheet.create({
  slots: { borderRadius: radius.m, backgroundColor: colors.paper, overflow: 'hidden' },
  slot: { flexDirection: 'row', alignItems: 'center', gap: space.s, paddingHorizontal: space.m, paddingVertical: 11 },
  slotBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.rule },
  attempts: { alignItems: 'center' },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: space.s },
  guess: { backgroundColor: colors.card, borderRadius: radius.m, padding: space.m, gap: 4, borderLeftWidth: 4,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.rule },
  nextClue: { paddingHorizontal: 2 },
});
