import { router } from "expo-router";
import { Pressable, View } from "react-native";
import {
  Button,
  Copy,
  Header,
  Icon,
  Panel,
  Screen,
  s,
} from "@/components/creditpick";
import { useCreditPick } from "@/state/creditpick-provider";
import { theme } from "@/theme";

export default function SettingsScreen() {
  const { threshold, setThreshold, reset } = useCreditPick();
  return (
    <Screen>
      <Header title="Settings" />
      <Panel style={{ gap: 12 }}>
        <Icon name="user" />
        <Copy style={s.sectionTitle}>Jamie Davis</Copy>
        <Copy style={s.small}>Your demo profile · No sign-in required</Copy>
      </Panel>
      <Panel style={{ gap: 16 }}>
        <Copy style={s.sectionTitle}>Utilization alert</Copy>
        <Copy style={s.small}>
          Choose a reminder threshold for this session.
        </Copy>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {[20, 30, 40].map((value) => (
            <Pressable
              key={value}
              accessibilityRole="radio"
              accessibilityState={{ checked: threshold === value }}
              accessibilityLabel={`${value}% alert threshold`}
              onPress={() => setThreshold(value)}
              style={{
                minWidth: 64,
                minHeight: 48,
                padding: 12,
                borderRadius: 12,
                backgroundColor:
                  threshold === value
                    ? theme.colors.accent
                    : theme.colors.accentSurface,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Copy
                style={{
                  color:
                    threshold === value
                      ? theme.colors.onAccent
                      : theme.colors.accent,
                }}
              >
                {value}%
              </Copy>
            </Pressable>
          ))}
        </View>
        <Copy style={s.small}>
          This is a personal reminder, not a guarantee of improving a credit
          score.
        </Copy>
      </Panel>
      <Panel style={{ gap: 12 }}>
        <Copy style={s.sectionTitle}>About this demo</Copy>
        <Copy style={s.small}>
          All cards, balances, and rewards are sample data. Voice input is
          scripted and never records audio. Recommendations can be read aloud
          using your device’s text-to-speech.
        </Copy>
        <Copy style={s.small}>
          Nothing is linked, synced, or saved to a server. Changes reset when
          the app restarts.
        </Copy>
      </Panel>
      <Button
        title="Reset demo"
        secondary
        icon="rotate-ccw"
        onPress={() => {
          reset();
          setThreshold(30);
          router.navigate("/");
        }}
      />
      <Copy style={[s.small, { textAlign: "center" }]}>
        CreditPick · A little clarity before you pay.
      </Copy>
    </Screen>
  );
}
