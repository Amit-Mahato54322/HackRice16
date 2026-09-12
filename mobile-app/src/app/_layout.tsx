import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { CreditPickProvider } from "@/state/creditpick-provider";
import { theme } from "@/theme";

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <CreditPickProvider>
        <StatusBar style="dark" />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: theme.colors.background },
          }}
        >
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="conversation" />
          <Stack.Screen name="recommendation" />
        </Stack>
      </CreditPickProvider>
    </SafeAreaProvider>
  );
}
