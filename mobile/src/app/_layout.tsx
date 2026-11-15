import { Fraunces_400Regular, Fraunces_400Regular_Italic, Fraunces_600SemiBold } from '@expo-google-fonts/fraunces';
import { Inter_400Regular, Inter_500Medium, Inter_600SemiBold } from '@expo-google-fonts/inter';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';

import { AuthProvider, useAuth } from '@/auth';
import { headerOptions } from '@/navigation';

SplashScreen.preventAutoHideAsync();

function RootStack() {
  const { ready } = useAuth();
  const [fontsLoaded] = useFonts({
    Fraunces_400Regular, Fraunces_400Regular_Italic, Fraunces_600SemiBold,
    Inter_400Regular, Inter_500Medium, Inter_600SemiBold,
  });
  const loaded = ready && fontsLoaded;

  useEffect(() => {
    if (loaded) SplashScreen.hideAsync();
  }, [loaded]);

  if (!loaded) return null;
  return (
    <>
      <StatusBar style="dark" />
      <Stack screenOptions={headerOptions}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="game/[id]" options={{ title: '' }} />
        <Stack.Screen name="wine/[slug]" options={{ title: '' }} />
        <Stack.Screen name="player/[username]" options={{ title: '' }} />
        <Stack.Screen name="auth" options={{ presentation: 'modal', title: '' }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootStack />
    </AuthProvider>
  );
}
