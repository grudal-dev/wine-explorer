import { Stack } from 'expo-router';

import { headerOptions } from '@/navigation';

export default function TabStack() {
  return <Stack screenOptions={headerOptions} />;
}
