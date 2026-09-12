import { Tabs } from "expo-router";
import { Icon, IconName } from "@/components/creditpick";
import { theme } from "@/theme";
export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: theme.colors.accent,
        tabBarInactiveTintColor: theme.colors.muted,
        tabBarStyle: {
          backgroundColor: theme.colors.surface,
          borderTopColor: theme.colors.border,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: "500" },
        tabBarItemStyle: { paddingTop: 6 },
      }}
    >
      {(
        [
          { name: "index", title: "Home", icon: "home" },
          { name: "wallet", title: "Wallet", icon: "credit-card" },
          { name: "settings", title: "Settings", icon: "settings" },
        ] as { name: string; title: string; icon: IconName }[]
      ).map((tab) => (
        <Tabs.Screen
          key={tab.name}
          name={tab.name}
          options={{
            title: tab.title,
            tabBarIcon: ({ color }) => (
              <Icon name={tab.icon} color={color} size={21} />
            ),
          }}
        />
      ))}
    </Tabs>
  );
}
