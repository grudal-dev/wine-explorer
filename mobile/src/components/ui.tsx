import Ionicons from '@expo/vector-icons/Ionicons';
import * as Haptics from 'expo-haptics';
import type { ComponentProps, ReactNode } from 'react';
import {
  ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View,
  type ScrollViewProps, type StyleProp, type TextStyle, type ViewStyle,
} from 'react-native';

import { API_URL, ApiError, NetworkError } from '@/api/client';
import { t } from '@/i18n';
import { colors, fonts, radius, shadow, space, type, verdictColors, wineColor } from '@/theme';

type IconName = ComponentProps<typeof Ionicons>['name'];

// ── Mise en page ─────────────────────────────────────────────────────────────
export function Screen({ children, refreshing, onRefresh, style, ...rest }:
  ScrollViewProps & { refreshing?: boolean; onRefresh?: () => void }) {
  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
      style={[{ flex: 1, backgroundColor: colors.paper }, style]}
      contentContainerStyle={styles.screen}
      refreshControl={onRefresh ? (
        <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={colors.garnet} />
      ) : undefined}
      {...rest}
    >
      {children}
    </ScrollView>
  );
}

export function Card({ children, style, tone }: { children: ReactNode; style?: StyleProp<ViewStyle>; tone?: 'wash' }) {
  return <View style={[styles.card, tone === 'wash' && styles.cardWash, style]}>{children}</View>;
}

export function Section({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <View style={{ gap: space.s }}>
      <View style={styles.sectionHead}>
        <Text style={type.caption}>{title}</Text>
        {right}
      </View>
      {children}
    </View>
  );
}

export function Row({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[{ flexDirection: 'row', alignItems: 'center', gap: space.s }, style]}>{children}</View>;
}

export const T = {
  Display: (p: { children: ReactNode; style?: StyleProp<TextStyle> }) => <Text style={[type.display, p.style]}>{p.children}</Text>,
  Title: (p: { children: ReactNode; style?: StyleProp<TextStyle> }) => <Text style={[type.title, p.style]}>{p.children}</Text>,
  Heading: (p: { children: ReactNode; style?: StyleProp<TextStyle>; numberOfLines?: number }) => (
    <Text style={[type.heading, p.style]} numberOfLines={p.numberOfLines}>{p.children}</Text>),
  Body: (p: { children: ReactNode; style?: StyleProp<TextStyle> }) => <Text style={[type.body, p.style]}>{p.children}</Text>,
  Small: (p: { children: ReactNode; style?: StyleProp<TextStyle>; numberOfLines?: number }) => (
    <Text style={[type.small, p.style]} numberOfLines={p.numberOfLines}>{p.children}</Text>),
  Caption: (p: { children: ReactNode; style?: StyleProp<TextStyle> }) => <Text style={[type.caption, p.style]}>{p.children}</Text>,
};

// ── Boutons ──────────────────────────────────────────────────────────────────
export function Button({ title, onPress, variant = 'primary', icon, disabled, loading, style }: {
  title: string; onPress: () => void; variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  icon?: IconName; disabled?: boolean; loading?: boolean; style?: StyleProp<ViewStyle>;
}) {
  const fg = variant === 'primary' ? colors.paper : variant === 'danger' ? colors.garnet : colors.ink;
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled || loading}
      onPress={() => { Haptics.selectionAsync(); onPress(); }}
      style={({ pressed }) => [
        styles.button, styles[`button_${variant}`],
        (disabled || loading) && { opacity: 0.45 }, pressed && { opacity: 0.8, transform: [{ scale: 0.985 }] }, style,
      ]}
    >
      {loading ? <ActivityIndicator color={fg} /> : (
        <>
          {icon && <Ionicons name={icon} size={18} color={fg} />}
          <Text style={[styles.buttonText, { color: fg }]}>{title}</Text>
        </>
      )}
    </Pressable>
  );
}

export function Segmented<K extends string>({ value, options, onChange }: {
  value: K; options: { key: K; label: string }[]; onChange: (k: K) => void;
}) {
  return (
    <View style={styles.segmented}>
      {options.map((o) => {
        const on = o.key === value;
        return (
          <Pressable key={o.key} onPress={() => { Haptics.selectionAsync(); onChange(o.key); }}
            accessibilityRole="tab" accessibilityState={{ selected: on }}
            style={[styles.segment, on && styles.segmentOn]}>
            <Text style={[styles.segmentText, on && { color: colors.ink, fontFamily: fonts.sansBold }]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function ListItem({ title, subtitle, left, right, onPress }: {
  title: string; subtitle?: string; left?: ReactNode; right?: ReactNode; onPress?: () => void;
}) {
  return (
    <Pressable onPress={onPress} disabled={!onPress}
      style={({ pressed }) => [styles.listItem, pressed && { backgroundColor: colors.chalk }]}>
      {left}
      <View style={{ flex: 1 }}>
        <Text style={[type.body, { fontFamily: fonts.sansMedium }]} numberOfLines={1}>{title}</Text>
        {subtitle ? <Text style={type.small} numberOfLines={1}>{subtitle}</Text> : null}
      </View>
      {right}
      {onPress && <Ionicons name="chevron-forward" size={16} color={colors.ink3} />}
    </Pressable>
  );
}

// ── Éléments du vin ──────────────────────────────────────────────────────────
export function Robe({ color, size = 14 }: { color?: string | null; size?: number }) {
  return <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: wineColor(color),
    borderWidth: StyleSheet.hairlineWidth, borderColor: 'rgba(0,0,0,0.15)' }} />;
}

export function Chip({ label, hue, intensity }: { label: string; hue?: string; intensity?: number }) {
  return (
    <View style={[styles.chip, hue ? { borderColor: hue } : null]}>
      {hue && <View style={[styles.chipDot, { backgroundColor: hue }]} />}
      <Text style={styles.chipText}>{label}</Text>
      {intensity ? <Text style={[styles.chipText, { color: colors.ink3 }]}>{'•'.repeat(intensity)}</Text> : null}
    </View>
  );
}

/** Jauge de structure en bouche, de 0 à 5. */
export function Meter({ label, value, max = 5 }: { label: string; value: number; max?: number }) {
  return (
    <View style={styles.meterRow} accessibilityLabel={`${label} ${value}/${max}`}>
      <Text style={[type.small, { width: 92 }]}>{label}</Text>
      <View style={{ flexDirection: 'row', gap: 5, flex: 1 }}>
        {Array.from({ length: max }, (_, i) => (
          <View key={i} style={[styles.meterCell, i < value && { backgroundColor: colors.garnet }]} />
        ))}
      </View>
    </View>
  );
}

export function Badge({ label, verdict, tone }: { label: string; verdict?: string; tone?: { fg: string; bg: string } }) {
  const c = tone || verdictColors[verdict || 'info'];
  return (
    <View style={[styles.badge, { backgroundColor: c.bg }]}>
      <Text style={[styles.badgeText, { color: c.fg }]}>{label}</Text>
    </View>
  );
}

export function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <View style={{ flex: 1, alignItems: 'center', gap: 2 }}>
      <Text style={type.number}>{value}</Text>
      <Text style={type.caption}>{label}</Text>
    </View>
  );
}

// ── États ────────────────────────────────────────────────────────────────────
export function Loading() {
  return <View style={styles.center}><ActivityIndicator color={colors.garnet} size="large" /></View>;
}

export function errorMessage(e: unknown): string {
  if (e instanceof NetworkError) return API_URL.startsWith('https') ? t.offlineRemote : t.offline;
  if (e instanceof ApiError) return e.message;
  return t.error;
}

export function ErrorView({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <View style={[styles.center, { padding: space.xl, gap: space.m, backgroundColor: colors.paper }]}>
      <Ionicons name={error instanceof NetworkError ? 'cloud-offline-outline' : 'alert-circle-outline'} size={40} color={colors.ink3} />
      <T.Body style={{ textAlign: 'center', color: colors.ink2 }}>{errorMessage(error)}</T.Body>
      {onRetry && <Button title={t.retry} variant="secondary" onPress={onRetry} />}
    </View>
  );
}

export function Notice({ text, tone = 'info' }: { text: string; tone?: 'info' | 'error' }) {
  const c = tone === 'error' ? { fg: colors.garnet, bg: colors.garnetWash } : { fg: colors.slate, bg: colors.slateWash };
  return (
    <View style={[styles.notice, { backgroundColor: c.bg }]}>
      <Text style={[type.small, { color: c.fg }]}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { padding: space.l, paddingBottom: space.xxl * 2, gap: space.xl },
  card: { backgroundColor: colors.card, borderRadius: radius.l, padding: space.l, gap: space.m,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.rule, ...shadow },
  cardWash: { backgroundColor: colors.chalk, shadowOpacity: 0, elevation: 0 },
  sectionHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 2 },
  button: { minHeight: 48, borderRadius: radius.m, paddingHorizontal: space.l, flexDirection: 'row',
    alignItems: 'center', justifyContent: 'center', gap: space.s },
  button_primary: { backgroundColor: colors.garnet },
  button_secondary: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.rule },
  button_ghost: { backgroundColor: 'transparent', minHeight: 40 },
  button_danger: { backgroundColor: colors.garnetWash },
  buttonText: { fontFamily: fonts.sansBold, fontSize: 16 },
  segmented: { flexDirection: 'row', backgroundColor: colors.chalk, borderRadius: radius.m, padding: 3 },
  segment: { flex: 1, paddingVertical: 8, borderRadius: radius.m - 3, alignItems: 'center' },
  segmentOn: { backgroundColor: colors.card, ...shadow },
  segmentText: { fontFamily: fonts.sansMedium, fontSize: 14, color: colors.ink2 },
  listItem: { flexDirection: 'row', alignItems: 'center', gap: space.m, paddingVertical: space.m, paddingHorizontal: space.l,
    backgroundColor: colors.card, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.rule },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 6,
    borderRadius: radius.pill, borderWidth: 1, borderColor: colors.rule, backgroundColor: colors.card },
  chipDot: { width: 8, height: 8, borderRadius: 4 },
  chipText: { fontFamily: fonts.sansMedium, fontSize: 14, color: colors.ink },
  meterRow: { flexDirection: 'row', alignItems: 'center' },
  meterCell: { flex: 1, height: 8, borderRadius: 4, backgroundColor: colors.chalk },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill, alignSelf: 'flex-start' },
  badgeText: { fontFamily: fonts.sansBold, fontSize: 12 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  notice: { borderRadius: radius.m, padding: space.m },
});
