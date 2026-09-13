import { Image, Pressable, StyleSheet, View } from "react-native";
import type { WalletCard as WalletCardData } from "@/services/contracts";
import { theme } from "@/theme";
import { cardArt } from "./card-art";
import { Copy, Icon, Leaf, s } from "./creditpick";

/** Standard credit-card proportions; grows vertically for accessibility text. */
export function WalletCard({
  card,
  width,
  onPress,
  index = 0,
}: {
  card: WalletCardData;
  width: number;
  onPress: () => void;
  index?: number;
}) {
  const art = cardArt(card.productId, card.issuer, index);
  const source = art.image ?? (card.artUrl ? { uri: card.artUrl } : undefined);

  // A real card image replaces the drawn face entirely; the details below sit
  // on top of the drawn one only.
  if (source) {
    return (
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${card.name}, ending in ${card.digits}. ${card.rewardSummary}. View card details`}
        onPress={onPress}
        style={({ pressed }) => [
          styles.card,
          { width, minHeight: width / 1.586, padding: 0, overflow: "hidden" },
          pressed && s.pressed,
        ]}
      >
        <Image
          source={source}
          style={{ width: "100%", height: width / 1.586 }}
          resizeMode="cover"
          accessible={false}
        />
      </Pressable>
    );
  }

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${card.name}, ending in ${card.digits}. ${card.rewardSummary}. View card details`}
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        { width, minHeight: width / 1.586, backgroundColor: art.background },
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
        <Icon name="wifi" size={22} color={art.accent} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: theme.radius.md,
    padding: 20,
    gap: 14,
    justifyContent: "space-between",
    backgroundColor: theme.colors.surface,
    boxShadow: theme.shadow.card,
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
