import Feather from "@expo/vector-icons/Feather";
import { router } from "expo-router";
import { ComponentProps, PropsWithChildren } from "react";
import {
  ActivityIndicator,
  ColorValue,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextProps,
  View,
  ViewProps,
  useWindowDimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { CreditCard, money } from "@/domain/models";
import type { WalletCard } from "@/services/contracts";
import { useCardCue } from "@/state/cardcue-provider";
import { theme } from "@/theme";

const c = theme.colors;
export type IconName = ComponentProps<typeof Feather>["name"];
export function Icon({
  name,
  size = 22,
  color = c.green,
}: {
  name: IconName;
  size?: number;
  color?: ColorValue;
}) {
  return <Feather name={name} size={size} color={color} accessible={false} />;
}
export function Copy({ style, ...props }: TextProps) {
  return <Text {...props} style={[s.copy, style]} />;
}
export function Panel({ style, ...props }: ViewProps) {
  return <View {...props} style={[s.panel, style]} />;
}
export function Badge({ children = "Demo" }: PropsWithChildren) {
  return (
    <View style={s.badge}>
      <Copy style={s.badgeText}>{children}</Copy>
    </View>
  );
}
export function Button({
  title,
  onPress,
  icon,
  loading = false,
  secondary = false,
}: {
  title: string;
  onPress: () => void;
  icon?: IconName;
  loading?: boolean;
  secondary?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled: loading, busy: loading }}
      disabled={loading}
      onPress={onPress}
      style={({ pressed }) => [
        s.button,
        secondary && s.secondary,
        pressed && s.pressed,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={c.surface} />
      ) : (
        <>
          <Copy style={[s.buttonText, secondary && { color: c.green }]}>
            {title}
          </Copy>
          {icon && (
            <Icon
              name={icon}
              color={secondary ? c.green : c.surface}
              size={20}
            />
          )}
        </>
      )}
    </Pressable>
  );
}
export function TextAction({
  title,
  onPress,
}: {
  title: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [s.textAction, pressed && s.pressed]}
    >
      <Copy style={s.link}>{title}</Copy>
    </Pressable>
  );
}
export function IconButton({
  name,
  label,
  onPress,
  filled = false,
}: {
  name: IconName;
  label: string;
  onPress: () => void;
  filled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [
        s.iconButton,
        filled && { backgroundColor: c.green },
        pressed && s.pressed,
      ]}
    >
      <Icon name={name} color={filled ? c.surface : c.green} />
    </Pressable>
  );
}
export function Header({
  title,
  back = false,
}: {
  title: string;
  back?: boolean;
}) {
  return (
    <View style={s.header}>
      {back && (
        <IconButton
          name="arrow-left"
          label="Go back"
          onPress={() =>
            router.canGoBack() ? router.back() : router.replace("/")
          }
        />
      )}
      <Copy accessibilityRole="header" style={s.headerTitle}>
        {title}
      </Copy>
      {!back && <Badge />}
    </View>
  );
}
export function Screen({
  children,
  bottom = false,
  fit = false,
}: PropsWithChildren<{ bottom?: boolean; fit?: boolean }>) {
  const { fontScale, height } = useWindowDimensions();
  const needsAccessibleScroll =
    fontScale > 1.15 || height < (bottom ? 780 : 650);
  const contentStyle = [
    s.content,
    fit && { gap: height < 740 ? 4 : 6, paddingTop: 4, paddingBottom: 8 },
  ];
  return (
    <SafeAreaView
      style={s.screen}
      edges={
        bottom ? ["top", "left", "right", "bottom"] : ["top", "left", "right"]
      }
    >
      {fit && !needsAccessibleScroll ? (
        <View
          style={[contentStyle, { flex: 1, justifyContent: "space-between" }]}
        >
          {children}
        </View>
      ) : (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={contentStyle}
        >
          {children}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
export function Leaf({ small = false }: { small?: boolean }) {
  return (
    <View
      accessible={false}
      style={{
        width: small ? 20 : 30,
        height: small ? 16 : 28,
        justifyContent: "center",
      }}
    >
      <View
        style={{
          width: small ? 13 : 22,
          height: small ? 20 : 30,
          borderTopLeftRadius: 20,
          borderBottomRightRadius: 20,
          backgroundColor: "#D2E8CF",
          transform: [{ rotate: "30deg" }],
        }}
      />
      <View
        style={{
          position: "absolute",
          width: 1.5,
          height: small ? 16 : 25,
          backgroundColor: "#739B75",
          left: small ? 6 : 10,
          top: small ? 10 : 13,
          transform: [{ rotate: "30deg" }],
        }}
      />
    </View>
  );
}
export function CardVisual({
  card,
  large = false,
  best = false,
  compact = false,
}: {
  card: CreditCard;
  large?: boolean;
  best?: boolean;
  compact?: boolean;
}) {
  return (
    <View
      accessibilityLabel={`${card.name}, ending in ${card.digits}`}
      style={[
        s.card,
        { backgroundColor: card.color },
        large ? s.largeCard : s.smallCard,
        compact && { minHeight: 120, padding: 12 },
      ]}
    >
      <View style={s.cardArc} />
      <View style={s.row}>
        <Leaf small={!large} />
        {large && best && (
          <View style={s.best}>
            <Icon name="check" size={12} color="#E6F2E5" />
            <Copy style={s.bestText}>Best match</Copy>
          </View>
        )}
      </View>
      {large && (
        <Copy style={[s.cardName, compact && { marginTop: 4, fontSize: 21 }]}>
          {card.name}
        </Copy>
      )}
      <View style={[s.row, { marginTop: large ? (compact ? 8 : 24) : 0 }]}>
        <Copy
          style={{
            color: "#F1F5EC",
            fontSize: large ? 17 : 8,
            lineHeight: large ? 24 : 10,
            letterSpacing: 2,
          }}
        >
          {large ? "•••• " : ""}
          {card.digits}
        </Copy>
        {large && <Icon name="wifi" color="#B6D4BD" size={22} />}
      </View>
    </View>
  );
}
export function CardRow({
  card,
  onPress,
  compact = false,
}: {
  card: WalletCard;
  onPress?: () => void;
  compact?: boolean;
}) {
  const content = (
    <>
      <CardVisual card={card} />
      <View style={{ flex: 1, gap: compact ? 2 : 5 }}>
        <Copy style={s.bold}>
          {card.name} <Copy style={s.small}>•••• {card.digits}</Copy>
        </Copy>
        <Copy style={s.small}>{card.rewardSummary}</Copy>
      </View>
      {onPress && <Icon name="chevron-right" size={18} color={c.muted} />}
    </>
  );
  return onPress ? (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`View ${card.name} details`}
      onPress={onPress}
      style={({ pressed }) => [
        s.cardRow,
        compact && { paddingVertical: 4 },
        pressed && s.pressed,
      ]}
    >
      {content}
    </Pressable>
  ) : (
    <View style={s.cardRow}>{content}</View>
  );
}
export function WalletSummary({
  compact = false,
  dense = false,
}: {
  compact?: boolean;
  dense?: boolean;
}) {
  const { threshold, wallet, walletError, reloadWallet } = useCardCue();
  if (walletError)
    return (
      <Panel>
        <Copy>{walletError}</Copy>
        <TextAction title="Retry" onPress={reloadWallet} />
      </Panel>
    );
  if (!wallet)
    return (
      <Panel>
        <ActivityIndicator
          color={c.green}
          accessibilityLabel="Loading wallet"
        />
      </Panel>
    );
  const utilization = wallet.utilization;
  return (
    <Panel
      style={{
        backgroundColor: "#EEF3EA",
        gap: dense ? 6 : compact ? 10 : 20,
        padding: dense ? 10 : compact ? 12 : 20,
      }}
    >
      {!dense && (
        <View style={s.row}>
          <Copy style={[s.bold, { flexShrink: 1 }]}>
            Your wallet at a glance
          </Copy>
          <Badge />
        </View>
      )}
      <View style={s.stats}>
        <View style={s.stat}>
          <Copy style={s.statValue}>{wallet.cards.length}</Copy>
          <Copy style={s.small}>cards connected</Copy>
        </View>
        <View style={[s.stat, s.statBorder]}>
          <Copy style={s.statValue}>{utilization}%</Copy>
          <Copy style={s.small}>utilization</Copy>
        </View>
        <View style={s.stat}>
          <Copy style={s.statValue}>{money(wallet.available)}</Copy>
          <Copy style={s.small}>available</Copy>
        </View>
      </View>
      <View style={{ gap: 8 }}>
        <View
          accessibilityLabel={`${utilization}% utilization; ${threshold}% alert threshold`}
          style={s.track}
        >
          <View style={[s.trackFill, { width: `${utilization}%` }]} />
          <View style={[s.marker, { left: `${threshold}%` }]} />
        </View>
        <View style={s.row}>
          <Copy style={s.tiny}>
            {dense ? "Demo utilization" : "Current utilization"}
          </Copy>
          <Copy style={s.tiny}>{threshold}% alert threshold</Copy>
        </View>
      </View>
    </Panel>
  );
}
export function ChatBubble({
  children,
  user = false,
}: PropsWithChildren<{ user?: boolean }>) {
  return (
    <View style={[s.bubble, user && s.userBubble]}>
      <Copy style={{ fontSize: 15, lineHeight: 22 }}>{children}</Copy>
    </View>
  );
}
export function Sheet({
  visible,
  title,
  onClose,
  children,
}: PropsWithChildren<{
  visible: boolean;
  title: string;
  onClose: () => void;
}>) {
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={s.modal}>
        <Pressable
          style={StyleSheet.absoluteFill}
          accessibilityLabel="Close dialog"
          accessibilityRole="button"
          onPress={onClose}
        />
        <SafeAreaView
          edges={["bottom"]}
          style={s.sheet}
          accessibilityViewIsModal
        >
          <View style={s.handle} />
          <View style={s.row}>
            <Copy
              accessibilityRole="header"
              style={[s.sectionTitle, { flex: 1 }]}
            >
              {title}
            </Copy>
            <IconButton name="x" label="Close dialog" onPress={onClose} />
          </View>
          <ScrollView
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={{ gap: 16, paddingBottom: 12 }}
          >
            {children}
          </ScrollView>
        </SafeAreaView>
      </View>
    </Modal>
  );
}
export const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: c.background },
  content: {
    flexGrow: 1,
    padding: theme.spacing.xl,
    paddingTop: 12,
    paddingBottom: 24,
    gap: theme.spacing.xl,
    width: "100%",
    maxWidth: 560,
    alignSelf: "center",
  },
  copy: { color: c.ink, fontSize: theme.type.body, lineHeight: 23 },
  bold: { fontWeight: "600" },
  small: { fontSize: 12, lineHeight: 18, color: c.muted },
  tiny: { fontSize: 10, lineHeight: 16, color: c.muted },
  panel: {
    padding: 20,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.border,
    borderRadius: theme.radius.md,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    backgroundColor: "#E0EBDD",
    borderRadius: 6,
  },
  badgeText: {
    color: c.green,
    fontSize: 10,
    lineHeight: 17,
    fontWeight: "600",
  },
  button: {
    minHeight: 56,
    borderRadius: 15,
    backgroundColor: c.green,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    padding: 16,
    gap: 12,
  },
  buttonText: {
    color: c.surface,
    fontWeight: "600",
    flexShrink: 1,
    textAlign: "center",
  },
  secondary: { backgroundColor: c.mint },
  pressed: { opacity: 0.65 },
  textAction: {
    minHeight: 44,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 4,
  },
  link: { fontSize: 14, fontWeight: "600", color: c.green },
  iconButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: "center",
    alignItems: "center",
  },
  header: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 48 },
  headerTitle: { fontSize: 22, lineHeight: 30, fontWeight: "600", flex: 1 },
  sectionTitle: { fontSize: 19, lineHeight: 27, fontWeight: "600" },
  card: { overflow: "hidden", justifyContent: "space-between" },
  smallCard: { width: 66, height: 42, borderRadius: 7, padding: 6 },
  largeCard: { borderRadius: 20, padding: 24, minHeight: 188 },
  cardArc: {
    position: "absolute",
    width: 250,
    height: 250,
    borderRadius: 125,
    borderColor: "#FFFFFF10",
    borderWidth: 35,
    right: -100,
    top: -85,
  },
  cardName: {
    color: "#F7FAF2",
    fontSize: 23,
    lineHeight: 30,
    fontWeight: "500",
    marginTop: 16,
  },
  best: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: "#FFFFFF20",
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  bestText: { color: "#E6F2E5", fontSize: 11, lineHeight: 17 },
  cardRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 13,
    paddingVertical: 16,
  },
  stats: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  stat: { flex: 1, minWidth: 70, gap: 4 },
  statBorder: { paddingLeft: 12, borderLeftWidth: 1, borderColor: "#D8E2D5" },
  statValue: {
    fontSize: 22,
    lineHeight: 28,
    fontWeight: "600",
    letterSpacing: -0.8,
  },
  track: { height: 7, borderRadius: 5, backgroundColor: "#DAE3D7" },
  trackFill: { height: 7, borderRadius: 5, backgroundColor: c.greenLight },
  marker: {
    width: 2,
    height: 15,
    position: "absolute",
    top: -4,
    backgroundColor: "#849581",
  },
  bubble: {
    alignSelf: "flex-start",
    maxWidth: "89%",
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: c.border,
    borderRadius: 17,
    borderBottomLeftRadius: 5,
  },
  userBubble: {
    alignSelf: "flex-end",
    backgroundColor: c.mint,
    borderColor: c.mint,
    borderBottomLeftRadius: 17,
    borderBottomRightRadius: 5,
  },
  modal: { flex: 1, backgroundColor: "#14291D66", justifyContent: "flex-end" },
  sheet: {
    backgroundColor: c.background,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    padding: 24,
    paddingTop: 12,
    maxHeight: "86%",
    gap: 12,
  },
  handle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#C9D2C7",
    alignSelf: "center",
  },
});
