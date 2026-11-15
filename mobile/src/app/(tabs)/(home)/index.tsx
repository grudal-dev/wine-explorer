import Ionicons from '@expo/vector-icons/Ionicons';
import { Stack, useRouter } from 'expo-router';
import { useEffect, useState, type ComponentProps } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';

import { api } from '@/api/client';
import { useAuth } from '@/auth';
import { Badge, Button, Card, ErrorView, Loading, Row, Screen, Section, T, errorMessage } from '@/components/ui';
import { useQuery } from '@/hooks/useQuery';
import { formatDay, t } from '@/i18n';
import { tabRootOptions } from '@/navigation';
import { colors, fonts, type } from '@/theme';

/** Compte à rebours jusqu'à minuit (heure du serveur), recalé à chaque rechargement des données. */
/** Compte à rebours jusqu'à minuit (heure du serveur), recalé à chaque rechargement des données. */
function useCountdown(seconds: number | undefined) {
  const [left, setLeft] = useState(seconds ?? 0);
  useEffect(() => {
    if (seconds === undefined) return;
    const end = Date.now() + seconds * 1000;
    const tick = () => setLeft(Math.max(0, Math.round((end - Date.now()) / 1000)));
    const first = setTimeout(tick, 0);
    const timer = setInterval(tick, 1000);
    return () => { clearTimeout(first); clearInterval(timer); };
  }, [seconds]);
  const h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), s = left % 60;
  return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

type State = 'todo' | 'playing' | 'done';
const stateBadge = (s: State) => ({
  todo: { label: t.toPlay, tone: { fg: colors.garnet, bg: colors.garnetWash } },
  playing: { label: t.inProgress, tone: { fg: colors.ochre, bg: colors.ochreWash } },
  done: { label: t.done, tone: { fg: colors.olive, bg: colors.oliveWash } },
}[s]);

function ChallengeCard({ icon, title, pitch, state, detail, onPress }: {
  icon: ComponentProps<typeof Ionicons>['name']; title: string; pitch: string; state: State; detail?: string; onPress: () => void;
}) {
  const badge = stateBadge(state);
  return (
    <Card>
      <Row style={{ justifyContent: 'space-between' }}>
        <Row>
          <View style={styles.icon}><Ionicons name={icon} size={20} color={colors.garnet} /></View>
          <T.Heading>{title}</T.Heading>
        </Row>
        <Badge label={badge.label} tone={badge.tone} />
      </Row>
      <T.Small>{pitch}</T.Small>
      {detail ? <Text style={[type.body, { fontFamily: fonts.serifBold }]}>{detail}</Text> : null}
      <Button title={state === 'todo' ? t.play : state === 'playing' ? t.resume : t.see}
        variant={state === 'done' ? 'secondary' : 'primary'} onPress={onPress} />
    </Card>
  );
}

export default function Home() {
  const router = useRouter();
  const { user } = useAuth();
  const { data, error, loading, refreshing, refresh, reload } = useQuery(api.today);
  const countdown = useCountdown(data?.seconds_left);
  const [starting, setStarting] = useState<string | null>(null);

  const start = async (mode: 'daily' | 'free', color = '') => {
    setStarting(mode + color);
    try {
      const game = await api.newGame(mode, color);
      router.push(`/game/${game.id}`);
    } catch (e) {
      Alert.alert(t.error, errorMessage(e));
    } finally {
      setStarting(null);
    }
  };

  const options = { ...tabRootOptions, title: t.today };
  if (loading && !data) return <><Stack.Screen options={options} /><Loading /></>;
  if (error && !data) return <><Stack.Screen options={options} /><ErrorView error={error} onRetry={reload} /></>;
  if (!data) return null;

  const bt = data.blindtest, hc = data.hotcold;
  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <Stack.Screen options={options} />
      <View style={{ gap: 2 }}>
        <T.Caption>{formatDay(data.day)}</T.Caption>
        <T.Small>{user ? `${user.username} · ` : ''}{t.newIn} <Text style={{ fontFamily: fonts.sansBold, color: colors.ink }}>{countdown}</Text></T.Small>
      </View>

      <Section title={t.dailyChallenges}>
        <ChallengeCard icon="wine" title={t.blindtest} pitch={t.blindtestPitch} state={bt.state}
          detail={bt.state === 'done' ? `${bt.status_label} · ${bt.score} ${t.points}` : undefined}
          onPress={() => (bt.game_id ? router.push(`/game/${bt.game_id}`) : start('daily'))} />
        <ChallengeCard icon="thermometer" title={t.hotcold} pitch={t.hotcoldPitch} state={hc.state}
          detail={hc.state === 'done' ? `${t.guesses(hc.guesses)} · ${hc.score} ${t.points}`
            : hc.state === 'playing' ? t.guesses(hc.guesses) : undefined}
          onPress={() => router.navigate('/hotcold')} />
      </Section>

      <Section title={t.freeGame}>
        <Card tone="wash">
          <T.Small>{t.blindtestPitch}</T.Small>
          <Row style={{ flexWrap: 'wrap' }}>
            {[{ key: '', label: t.anyColor }, ...data.colors].map((c) => (
              <Button key={c.key || 'all'} title={c.label} variant="secondary" style={{ flexGrow: 1 }}
                loading={starting === 'free' + c.key} onPress={() => start('free', c.key)}
                icon={c.key ? undefined : 'shuffle'} />
            ))}
          </Row>
        </Card>
      </Section>

      <T.Small style={{ textAlign: 'center', color: colors.ink3 }}>{t.drinkResponsibly}</T.Small>
    </Screen>
  );
}

const styles = StyleSheet.create({
  icon: { width: 34, height: 34, borderRadius: 17, backgroundColor: colors.garnetWash, alignItems: 'center', justifyContent: 'center' },
});
