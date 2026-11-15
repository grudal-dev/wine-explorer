import { Platform } from 'react-native';

import { colors, fonts } from '@/theme';

/** Options d'en-tête communes : titres en Fraunces, grenat pour les actions. */
export const headerOptions = {
  headerTintColor: colors.garnet,
  headerTitleStyle: { fontFamily: fonts.serifBold, color: colors.ink },
  headerLargeTitleStyle: { fontFamily: fonts.serifBold, color: colors.ink },
  headerBackButtonDisplayMode: 'minimal' as const,
  headerShadowVisible: false,
  contentStyle: { backgroundColor: colors.paper },
  ...(Platform.OS === 'android' ? { headerStyle: { backgroundColor: colors.paper } } : {}),
};

/** Écran racine d'un onglet : grand titre natif sur iOS. */
export const tabRootOptions = { headerLargeTitle: true };
