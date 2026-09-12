import { router } from "expo-router";
import { Pressable, StyleSheet, View, useWindowDimensions } from "react-native";
import {
  CardRow,
  Copy,
  Icon,
  Screen,
  s,
  TextAction,
  WalletSummary,
} from "@/components/creditpick";
import { useCreditPick } from "@/state/creditpick-provider";
import { theme } from "@/theme";
export default function HomeScreen() {
  const { reset, wallet } = useCreditPick();
  const { height } = useWindowDimensions();
  const small = height < 850;
  const comparisonCards =
    wallet?.cards.filter((card) => wallet.featuredCardIds.includes(card.id)) ??
    [];
  function start(typing = false) {
    reset();
    router.push({
      pathname: "/conversation",
      params: { typing: typing ? "1" : "0" },
    });
  }
  return (
    <Screen fit>
      <View style={s.row}>
        <Copy style={styles.wordmark}>
          CreditPick<Copy style={{ color: theme.colors.accentBright }}>.</Copy>
        </Copy>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Open profile and settings"
          onPress={() => router.navigate("/settings")}
          style={styles.avatar}
        >
          <Copy style={{ color: theme.colors.accent, fontWeight: "600" }}>
            JD
          </Copy>
        </Pressable>
      </View>
      <Copy
        accessibilityRole="header"
        style={[styles.heading, small && { fontSize: 25, lineHeight: 29 }]}
      >
        Choose your next{"\n"}card wisely.
      </Copy>
      <WalletSummary compact dense={height < 740} />
      <View>
        <View style={s.row}>
          <Copy style={s.sectionTitle}>Your cards</Copy>
          <TextAction
            title="View all"
            onPress={() => router.navigate("/wallet")}
          />
        </View>
        {comparisonCards.map((card, index) => (
          <View key={card.id} style={index === 0 && styles.divider}>
            <CardRow
              card={card}
              compact
              onPress={() =>
                router.navigate({
                  pathname: "/wallet",
                  params: { card: card.id },
                })
              }
            />
          </View>
        ))}
      </View>
      <View style={[styles.ask, small && { flexDirection: "row", gap: 16 }]}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Start simulated voice conversation"
          onPress={() => start()}
          style={({ pressed }) => [styles.microphone, pressed && s.pressed]}
        >
          <Icon name="mic" size={32} color={theme.colors.onAccent} />
        </Pressable>
        <View style={{ alignItems: "center", gap: 0, flexShrink: 1 }}>
          <Copy style={styles.askTitle}>What are you buying?</Copy>
          <Copy style={{ color: theme.colors.muted, fontSize: 14 }}>
            Tell us the store and amount.
          </Copy>
          <TextAction title="Type instead" onPress={() => start(true)} />
          {!small && (
            <Copy style={[s.small, { textAlign: "center" }]}>
              Demo data · Voice is simulated
            </Copy>
          )}
        </View>
      </View>
    </Screen>
  );
}
const styles = StyleSheet.create({
  wordmark: {
    fontSize: 27,
    lineHeight: 35,
    fontWeight: "700",
    letterSpacing: -1.2,
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: theme.colors.accentSurface,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  heading: {
    fontSize: 29,
    lineHeight: 34,
    fontWeight: "600",
    letterSpacing: -1.2,
  },
  divider: { borderBottomWidth: 1, borderBottomColor: theme.colors.border },
  ask: {
    alignItems: "center",
    paddingTop: 0,
    gap: 4,
    justifyContent: "center",
  },
  microphone: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: theme.colors.accent,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 0,
    boxShadow: "0px 6px 20px #00000040",
  },
  askTitle: {
    fontSize: 19,
    lineHeight: 25,
    fontWeight: "600",
    letterSpacing: -0.5,
  },
});
