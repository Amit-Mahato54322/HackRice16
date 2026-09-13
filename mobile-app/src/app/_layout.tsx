import { DefaultTheme, Stack, ThemeProvider } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { CreditPickProvider } from "@/state/creditpick-provider";
import { theme } from "@/theme";

const navigationTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: theme.colors.accent,
    background: theme.colors.background,
    card: theme.colors.surface,
    text: theme.colors.ink,
    border: theme.colors.border,
    notification: theme.colors.accent,
  },
};

export default function RootLayout() {
  return (
    <ThemeProvider value={navigationTheme}>
      <SafeAreaProvider>
        <CreditPickProvider>
          <StatusBar style="dark" />
          <Stack
            screenOptions={{
              headerShown: false,
              contentStyle: { backgroundColor: theme.colors.background },
            }}
          >
            <Stack.Screen name="index" />
            <Stack.Screen name="conversation" />
            <Stack.Screen name="recommendation" />
          </Stack>
        </CreditPickProvider>
      </SafeAreaProvider>
    </ThemeProvider>
  );
}
