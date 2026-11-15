import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

import { ApiError } from '@/api/client';
import { useAuth } from '@/auth';
import { Button, Notice, Screen, Segmented, T, errorMessage } from '@/components/ui';
import { t } from '@/i18n';
import { colors, fonts, radius, space, type } from '@/theme';

type Mode = 'login' | 'signup' | 'delete';

function Field({ label, error, ...props }: React.ComponentProps<typeof TextInput> & { label: string; error?: string[] }) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={type.caption}>{label}</Text>
      <TextInput placeholderTextColor={colors.ink3} autoCapitalize="none" autoCorrect={false}
        style={[styles.input, error && { borderColor: colors.garnet }]} accessibilityLabel={label} {...props} />
      {error?.map((e) => <Text key={e} style={[type.small, { color: colors.garnet }]}>{e}</Text>)}
    </View>
  );
}

function Check({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <Pressable onPress={() => onChange(!value)} style={styles.check} accessibilityRole="switch" accessibilityState={{ checked: value }}>
      <Text style={[type.body, { flex: 1 }]}>{label}</Text>
      <Switch value={value} onValueChange={onChange} trackColor={{ true: colors.garnet, false: colors.rule }} />
    </Pressable>
  );
}

export default function Auth() {
  const params = useLocalSearchParams<{ mode?: Mode }>();
  const router = useRouter();
  const { signIn, signUp, deleteAccount } = useAuth();
  const [mode, setMode] = useState<Mode>(params.mode === 'signup' || params.mode === 'delete' ? params.mode : 'login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [adult, setAdult] = useState(false);
  const [newsletter, setNewsletter] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string[]>>({});

  const submit = async () => {
    setBusy(true);
    setError(null);
    setFields({});
    try {
      if (mode === 'login') await signIn(username.trim(), password);
      else if (mode === 'signup') await signUp({ username: username.trim(), email: email.trim(), password, adult, newsletter });
      else await deleteAccount(password);
      router.back();
    } catch (e) {
      setError(errorMessage(e));
      if (e instanceof ApiError) setFields(e.fields);
    } finally {
      setBusy(false);
    }
  };

  const title = mode === 'login' ? t.signIn : mode === 'signup' ? t.signUp : t.deleteAccount;
  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen>
        <Stack.Screen options={{ title }} />
        {mode === 'delete' ? (
          <Notice text={t.deleteAccountText} tone="error" />
        ) : (
          <Segmented value={mode} onChange={(m) => { setMode(m); setError(null); setFields({}); }}
            options={[{ key: 'login', label: t.signIn }, { key: 'signup', label: t.signUp }]} />
        )}

        <View style={{ gap: space.l }}>
          {mode !== 'delete' && (
            <Field label={mode === 'login' ? t.usernameOrEmail : t.username} value={username} onChangeText={setUsername}
              textContentType="username" autoComplete="username" error={fields.username} />
          )}
          {mode === 'signup' && (
            <Field label={t.email} value={email} onChangeText={setEmail} keyboardType="email-address"
              textContentType="emailAddress" autoComplete="email" error={fields.email} />
          )}
          <Field label={t.password} value={password} onChangeText={setPassword} secureTextEntry
            textContentType={mode === 'signup' ? 'newPassword' : 'password'}
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            onSubmitEditing={submit} returnKeyType="go" error={fields.password} />
          {mode === 'signup' && (
            <View style={{ gap: space.s }}>
              <Check label={t.adult} value={adult} onChange={setAdult} />
              {fields.adult?.map((e) => <Text key={e} style={[type.small, { color: colors.garnet }]}>{e}</Text>)}
              <Check label={t.newsletter} value={newsletter} onChange={setNewsletter} />
            </View>
          )}
        </View>

        {error && Object.keys(fields).length === 0 && <Notice text={error} tone="error" />}
        <Button title={title} loading={busy} variant={mode === 'delete' ? 'danger' : 'primary'}
          disabled={!password || (mode !== 'delete' && !username) || (mode === 'signup' && !adult)} onPress={submit} />
        {mode === 'signup' && <T.Small style={{ textAlign: 'center' }}>{t.drinkResponsibly}</T.Small>}
      </Screen>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  input: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.rule, borderRadius: radius.m,
    paddingHorizontal: space.m, paddingVertical: 13, fontFamily: fonts.sans, fontSize: 17, color: colors.ink },
  check: { flexDirection: 'row', alignItems: 'center', gap: space.m, paddingVertical: 4 },
});
