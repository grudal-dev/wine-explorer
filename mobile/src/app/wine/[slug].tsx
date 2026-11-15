import { Stack, useLocalSearchParams } from 'expo-router';
import { useCallback } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { api } from '@/api/client';
import { Card, Chip, ErrorView, Loading, Meter, Robe, Row, Screen, Section, T } from '@/components/ui';
import { useQuery } from '@/hooks/useQuery';
import { t } from '@/i18n';
import { colors, fonts, space, type } from '@/theme';

export default function WineScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const fetcher = useCallback(() => api.wine(slug), [slug]);
  const { data: w, error, loading, reload } = useQuery(fetcher);

  if (loading && !w) return <Loading />;
  if (error && !w) return <ErrorView error={error} onRetry={reload} />;
  if (!w) return null;

  const facts = [
    w.price_min ? { label: t.price, value: `${w.price_min}–${w.price_max} €` } : null,
    w.serving_temp ? { label: t.serving, value: w.serving_temp } : null,
    w.aging_max ? { label: t.aging, value: `${w.aging_min}–${w.aging_max} ${t.years}` } : null,
  ].filter(Boolean) as { label: string; value: string }[];

  return (
    <Screen>
      <Stack.Screen options={{ title: w.appellation }} />
      <View style={{ gap: space.s }}>
        <Row><Robe color={w.color} size={18} /><T.Caption>{w.color_label} · {w.style}</T.Caption></Row>
        <T.Display>{w.name}</T.Display>
        <T.Small>{[w.subregion, w.region].filter(Boolean).join(', ')}</T.Small>
      </View>

      {w.description ? <T.Body style={styles.lede}>{w.description}</T.Body> : null}

      <Section title={t.grapes}>
        <Card style={{ gap: space.s }}>
          {w.grapes.map((g) => (
            <View key={g.name} style={{ gap: 4 }}>
              <Row style={{ justifyContent: 'space-between' }}>
                <Text style={[type.body, { fontFamily: fonts.sansMedium }]}>{g.name}</Text>
                <Text style={type.small}>{g.share} %</Text>
              </Row>
              <View style={styles.track}><View style={[styles.fill, { width: `${g.share}%` }]} /></View>
            </View>
          ))}
        </Card>
      </Section>

      <Section title={t.aromas}>
        <View style={styles.wrap}>
          {w.aromas.map((a) => <Chip key={a.name} label={a.name} hue={a.hue} intensity={a.intensity} />)}
        </View>
      </Section>

      <Section title={t.structure}>
        <Card style={{ gap: space.s }}>
          {w.structure.map((s) => <Meter key={s.label} label={s.label} value={s.value} />)}
        </Card>
      </Section>

      {w.pairings.length > 0 && (
        <Section title={t.pairings}>
          <T.Body>{w.pairings.join(' · ')}</T.Body>
        </Section>
      )}

      {facts.length > 0 && (
        <Card tone="wash">
          {facts.map((f) => (
            <Row key={f.label} style={{ justifyContent: 'space-between' }}>
              <T.Small>{f.label}</T.Small>
              <Text style={[type.body, { fontFamily: fonts.serifBold }]}>{f.value}</Text>
            </Row>
          ))}
        </Card>
      )}

      <T.Small style={{ textAlign: 'center', color: colors.ink3 }}>{t.drinkResponsibly}</T.Small>
    </Screen>
  );
}

const styles = StyleSheet.create({
  lede: { fontFamily: fonts.serifItalic, fontSize: 18, lineHeight: 27, color: colors.ink2 },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: space.s },
  track: { height: 6, borderRadius: 3, backgroundColor: colors.chalk, overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3, backgroundColor: colors.garnet },
});
