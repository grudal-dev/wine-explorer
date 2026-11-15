/**
 * Charte de Wine Explorer, reprise du site (static/css/app.css) pour que l'appli et le site
 * se reconnaissent : papier clair, encre, grenat ; Fraunces pour les titres et les chiffres,
 * Inter pour le texte.
 */
import { Platform } from 'react-native';

export const colors = {
  paper: '#F8F8F4',
  chalk: '#ECECE6',
  card: '#FFFFFF',
  ink: '#23262F',
  ink2: '#5B5F69',
  ink3: '#8A8D94',
  rule: '#D4D4CB',
  garnet: '#7A1F3D',
  garnet2: '#5E1630',
  garnetWash: '#F1E3E7',
  olive: '#56662D',
  oliveWash: '#E7EBDA',
  ochre: '#B07D22',
  ochreWash: '#F3EAD6',
  slate: '#3B5878',
  slateWash: '#E1E7EE',
  wine: { rouge: '#6B1730', blanc: '#D9C36A', rose: '#E59A8E' } as Record<string, string>,
};

export const fonts = {
  serif: 'Fraunces_400Regular',
  serifItalic: 'Fraunces_400Regular_Italic',
  serifBold: 'Fraunces_600SemiBold',
  sans: 'Inter_400Regular',
  sansMedium: 'Inter_500Medium',
  sansBold: 'Inter_600SemiBold',
};

export const space = { xs: 4, s: 8, m: 12, l: 16, xl: 24, xxl: 32 };
export const radius = { s: 6, m: 12, l: 18, pill: 999 };

export const type = {
  display: { fontFamily: fonts.serifBold, fontSize: 34, lineHeight: 40, color: colors.ink, letterSpacing: -0.4 },
  title: { fontFamily: fonts.serifBold, fontSize: 24, lineHeight: 30, color: colors.ink },
  heading: { fontFamily: fonts.serifBold, fontSize: 19, lineHeight: 24, color: colors.ink },
  body: { fontFamily: fonts.sans, fontSize: 16, lineHeight: 23, color: colors.ink },
  small: { fontFamily: fonts.sans, fontSize: 14, lineHeight: 20, color: colors.ink2 },
  caption: { fontFamily: fonts.sansMedium, fontSize: 12, lineHeight: 16, color: colors.ink3, letterSpacing: 0.6, textTransform: 'uppercase' as const },
  number: { fontFamily: fonts.serifBold, fontSize: 28, lineHeight: 32, color: colors.ink },
};

export const shadow = Platform.select({
  ios: { shadowColor: '#23262F', shadowOpacity: 0.06, shadowRadius: 10, shadowOffset: { width: 0, height: 3 } },
  default: { elevation: 1 },
});

/** Couleur d'un verdict de blind test. */
export const verdictColors: Record<string, { fg: string; bg: string }> = {
  hit: { fg: colors.olive, bg: colors.oliveWash },
  close: { fg: colors.ochre, bg: colors.ochreWash },
  miss: { fg: colors.ink2, bg: colors.chalk },
  info: { fg: colors.slate, bg: colors.slateWash },
};

export const wineColor = (key?: string | null) => (key && colors.wine[key]) || colors.ink3;
