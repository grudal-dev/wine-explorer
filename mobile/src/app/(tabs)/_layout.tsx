import { NativeTabs } from 'expo-router/native-tabs';

import { t } from '@/i18n';
import { colors } from '@/theme';

export default function TabsLayout() {
  return (
    <NativeTabs tintColor={colors.garnet}>
      <NativeTabs.Trigger name="(home)">
        <NativeTabs.Trigger.Icon sf={{ default: 'sun.max', selected: 'sun.max.fill' }} md="today" />
        <NativeTabs.Trigger.Label>{t.today}</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="blindtest">
        <NativeTabs.Trigger.Icon sf={{ default: 'wineglass', selected: 'wineglass.fill' }} md="wine_bar" />
        <NativeTabs.Trigger.Label>{t.blindtest}</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="hotcold">
        <NativeTabs.Trigger.Icon sf={{ default: 'thermometer.medium', selected: 'thermometer.high' }} md="device_thermostat" />
        <NativeTabs.Trigger.Label>{t.hotcold}</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="ranking">
        <NativeTabs.Trigger.Icon sf={{ default: 'trophy', selected: 'trophy.fill' }} md="emoji_events" />
        <NativeTabs.Trigger.Label>{t.ranking}</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="profile">
        <NativeTabs.Trigger.Icon sf={{ default: 'person.crop.circle', selected: 'person.crop.circle.fill' }} md="account_circle" />
        <NativeTabs.Trigger.Label>{t.profile}</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
