import Ionicons from '@expo/vector-icons/Ionicons';
import { Stack, useRouter } from 'expo-router';
import { View } from 'react-native';

import { api } from '@/api/client';
import { useAuth } from '@/auth';
import { PlayerView } from '@/components/PlayerView';
import { Button, Card, ErrorView, Loading, Row, Screen, T } from '@/components/ui';
import { useQuery } from '@/hooks/useQuery';
import { t } from '@/i18n';
import { tabRootOptions } from '@/navigation';
import { colors, space } from '@/theme';

function Guest() {
  const router = useRouter();
  return (
    <Card style={{ alignItems: 'center', paddingVertical: space.xl }}>
      <Ionicons name="person-circle-outline" size={56} color={colors.garnet} />
      <T.Title>{t.guestTitle}</T.Title>
      <T.Small style={{ textAlign: 'center' }}>{t.guestText}</T.Small>
      <Button title={t.signUp} style={{ alignSelf: 'stretch' }} onPress={() => router.push('/auth?mode=signup')} />
      <Button title={t.signIn} variant="secondary" style={{ alignSelf: 'stretch' }} onPress={() => router.push('/auth?mode=login')} />
    </Card>
  );
}

function Account() {
  const router = useRouter();
  const { signOut } = useAuth();
  const { data, error, loading, refreshing, refresh, reload } = useQuery(api.me);

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorView error={error} onRetry={reload} />;
  if (!data) return null;

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <Stack.Screen options={{ ...tabRootOptions, title: data.user.username }} />
      <T.Small>{data.user.email}</T.Small>
      <PlayerView stats={data.stats} games={data.games} hotcold={data.hotcold} self />
      <View style={{ gap: space.s }}>
        <Button title={t.signOut} variant="secondary" icon="log-out-outline" onPress={signOut} />
        <Row style={{ justifyContent: 'center' }}>
          <Button title={t.deleteAccount} variant="ghost" onPress={() => router.push('/auth?mode=delete')} />
        </Row>
      </View>
    </Screen>
  );
}

export default function Profile() {
  const { signedIn } = useAuth();
  if (signedIn) return <Account />;
  return (
    <Screen>
      <Stack.Screen options={{ ...tabRootOptions, title: t.profile }} />
      <Guest />
    </Screen>
  );
}
