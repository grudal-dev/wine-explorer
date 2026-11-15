import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Keyboard, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import type { Suggestion } from '@/api/types';
import { t } from '@/i18n';
import { colors, fonts, radius, space, type } from '@/theme';

/**
 * Saisie d'un essai avec suggestions au fil de la frappe. Choisir une suggestion lève toute
 * ambiguïté (« Cassis » l'appellation ou l'arôme) ; valider le texte libre laisse le serveur choisir.
 */
export function GuessInput({ placeholder, suggest, onSubmit, disabled }: {
  placeholder: string;
  suggest: (q: string) => Promise<Suggestion[]>;
  onSubmit: (q: string, choice: string) => Promise<boolean>;
  disabled?: boolean;
}) {
  const [q, setQ] = useState('');
  const [items, setItems] = useState<Suggestion[]>([]);
  const [busy, setBusy] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const text = q.trim();
    if (text.length < 2) return;
    const id = ++seq.current;
    const timer = setTimeout(() => {
      suggest(text).then((r) => { if (id === seq.current) setItems(r.slice(0, 6)); }).catch(() => undefined);
    }, 180);
    return () => clearTimeout(timer);
  }, [q, suggest]);

  const visible = q.trim().length < 2 ? [] : items;

  const submit = async (choice = '', label = q) => {
    if (busy || (!label.trim() && !choice)) return;
    setBusy(true);
    seq.current++;
    setItems([]);
    const ok = await onSubmit(label.trim(), choice);
    setBusy(false);
    if (ok) setQ('');
  };

  return (
    <View style={{ gap: space.s }}>
      <View style={[styles.field, disabled && { opacity: 0.5 }]}>
        <Ionicons name="search" size={18} color={colors.ink3} />
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder={placeholder}
          placeholderTextColor={colors.ink3}
          style={styles.input}
          autoCorrect={false}
          autoCapitalize="none"
          returnKeyType="send"
          editable={!disabled && !busy}
          onSubmitEditing={() => submit()}
          accessibilityLabel={placeholder}
        />
        {busy ? <ActivityIndicator color={colors.garnet} /> : (
          <Pressable onPress={() => submit()} disabled={!q.trim() || disabled} hitSlop={10}
            accessibilityRole="button" accessibilityLabel={t.propose}
            style={[styles.send, !q.trim() && { backgroundColor: colors.rule }]}>
            <Ionicons name="arrow-up" size={18} color={colors.paper} />
          </Pressable>
        )}
      </View>
      {visible.length > 0 && (
        <View style={styles.list}>
          {visible.map((s, i) => (
            <Pressable key={s.key} onPress={() => { Keyboard.dismiss(); submit(s.choice, s.label); }}
              style={({ pressed }) => [styles.item, i > 0 && styles.itemBorder, pressed && { backgroundColor: colors.chalk }]}>
              <Text style={[type.body, { flex: 1 }]} numberOfLines={1}>{s.label}</Text>
              <Text style={type.caption}>{s.hint}</Text>
            </Pressable>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  field: { flexDirection: 'row', alignItems: 'center', gap: space.s, backgroundColor: colors.card,
    borderRadius: radius.m, borderWidth: 1, borderColor: colors.rule, paddingLeft: space.m, paddingRight: 6, minHeight: 52 },
  input: { flex: 1, fontFamily: fonts.sans, fontSize: 17, color: colors.ink, paddingVertical: 12 },
  send: { width: 38, height: 38, borderRadius: 19, backgroundColor: colors.garnet, alignItems: 'center', justifyContent: 'center' },
  list: { backgroundColor: colors.card, borderRadius: radius.m, borderWidth: 1, borderColor: colors.rule, overflow: 'hidden' },
  item: { flexDirection: 'row', alignItems: 'center', gap: space.m, paddingHorizontal: space.l, paddingVertical: 12 },
  itemBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.rule },
});
