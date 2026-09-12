import { Pressable, StyleSheet, View } from "react-native";
import type { WalletCard as WalletCardData } from "@/services/contracts";
import { theme } from "@/theme";
import { Copy, Icon, Leaf, s } from "./creditpick";

/** Standard credit-card proportions; grows vertically for accessibility text. */
export function WalletCard({
  card,
  width,
  onPress,
}: {
  card: WalletCardData;
  width: number;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${card.name}, ending in ${card.digits}. ${card.rewardSummary}. View card details`}
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        { width, minHeight: width / 1.586, backgroundColor: card.color },
        pressed && s.pressed,
      ]}
    >
      <View style={styles.top}>
        <Leaf small />
      </View>
      <Copy style={styles.name}>{card.name}</Copy>
      <View style={styles.bottom}>
        <View style={styles.details}>
          <Copy style={styles.digits}>•••• •••• •••• {card.digits}</Copy>
          <Copy style={styles.reward}>{card.rewardSummary}</Copy>
        </View>
        <Icon name="wifi" size={22} color={theme.colors.cardMark} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 18,
    padding: 20,
    gap: 14,
    justifyContent: "space-between",
    borderWidth: 1,
    borderColor: theme.colors.track,
  },
  top: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  name: {
    fontSize: 23,
    lineHeight: 29,
    fontWeight: "600",
    color: theme.colors.cardInk,
  },
  bottom: { flexDirection: "row", alignItems: "center", gap: 10 },
  details: { flex: 1, gap: 5 },
  digits: {
    fontSize: 14,
    lineHeight: 20,
    letterSpacing: 1.1,
    color: theme.colors.cardInk,
  },
  reward: { fontSize: 12, lineHeight: 18, color: theme.colors.cardInk },
});
