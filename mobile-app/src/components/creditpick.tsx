import Feather from "@expo/vector-icons/Feather";
import { router } from "expo-router";
import { ComponentProps, PropsWithChildren } from "react";
import {
  Image,
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
import { CreditCard } from "@/domain/models";
import { cardArt } from "./card-art";
import type { WalletCard } from "@/services/contracts";
import { theme } from "@/theme";

const c = theme.colors;
export type IconName = ComponentProps<typeof Feather>["name"];
export function Icon({
  name,
  size = 22,
  color = c.accent,
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
export function Badge({ children }: PropsWithChildren) {
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
  disabled = false,
}: {
  title: string;
  onPress: () => void;
  icon?: IconName;
  loading?: boolean;
  secondary?: boolean;
  disabled?: boolean;
}) {
  const inactive = loading || disabled;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled: inactive, busy: loading }}
      disabled={inactive}
      onPress={onPress}
      style={({ pressed }) => [
        s.button,
        secondary && s.secondary,
        disabled && s.buttonDisabled,
        pressed && s.pressed,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={secondary ? c.accent : c.onAccent} />
      ) : (
        <>
          <Copy style={[s.buttonText, secondary && { color: c.accent }]}>
            {title}
          </Copy>
          {icon && (
            <Icon
              name={icon}
              color={secondary ? c.accent : c.onAccent}
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
        filled && { backgroundColor: c.accent },
        pressed && s.pressed,
      ]}
    >
      <Icon name={name} color={filled ? c.onAccent : c.accent} />
    </Pressable>
  );
}
export function Header({
  title,
  back = false,
  onBack,
}: {
  title: string;
  back?: boolean;
  onBack?: () => void;
}) {
  return (
    <View style={s.header}>
      {back && (
        <IconButton
          name="arrow-left"
          label={onBack ? "Back to Home" : "Go back"}
          onPress={
            onBack ??
            (() => (router.canGoBack() ? router.back() : router.replace("/")))
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
          style={{ flex: 1 }}
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
          backgroundColor: c.cardMark,
          transform: [{ rotate: "30deg" }],
        }}
      />
      <View
        style={{
          position: "absolute",
          width: 1.5,
          height: small ? 16 : 25,
          backgroundColor: c.cardMarkStem,
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
  card: CreditCard & { productId?: string; issuer?: string; artUrl?: string };
  large?: boolean;
  best?: boolean;
  compact?: boolean;
}) {
  const art = cardArt(card.productId, card.issuer, 0);
  const source = art.image ?? (card.artUrl ? { uri: card.artUrl } : undefined);

  // Real artwork stands on its own; the drawn face is the fallback.
  if (source) {
    return (
      <View
        accessibilityLabel={`${card.name}, ending in ${card.digits}`}
        style={[
          s.card,
          large ? s.largeCard : s.smallCard,
          compact && { minHeight: 120 },
          { padding: 0, overflow: "hidden", backgroundColor: art.background },
        ]}
      >
        <Image
          source={source}
          // A percentage height inside a minHeight-only parent (s.largeCard)
          // is ambiguous for Yoga's native layout and was inflating to fill
          // the whole screen on device (RN Web's CSS engine resolved the
          // same styles fine, which is why this only showed up on phone).
          // absoluteFillObject sizes against the parent's actual computed
          // box instead.
          style={StyleSheet.absoluteFill}
          resizeMode="cover"
          accessible={false}
        />
        {large && best && (
          <View style={[s.best, { position: "absolute", top: 12, right: 12 }]}>
            <Icon name="check" size={12} color={c.cardInk} />
            <Copy style={s.bestText}>Best match</Copy>
          </View>
        )}
      </View>
    );
  }

  return (
    <View
      accessibilityLabel={`${card.name}, ending in ${card.digits}`}
      style={[
        s.card,
        { backgroundColor: art.background },
        large ? s.largeCard : s.smallCard,
        compact && { minHeight: 120, padding: 12 },
      ]}
    >
      <View style={s.cardArc} />
      <View style={s.row}>
        <Leaf small={!large} />
        {large && best && (
          <View style={s.best}>
            <Icon name="check" size={12} color={c.cardInk} />
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
            color: c.cardInk,
            fontSize: large ? 17 : 8,
            lineHeight: large ? 24 : 10,
            letterSpacing: 2,
          }}
        >
          {large ? "•••• " : ""}
          {card.digits}
        </Copy>
        {large && <Icon name="wifi" color={art.accent} size={22} />}
      </View>
    </View>
  );
}
export function CardRow({
  card,
  onPress,
  compact = false,
  prominent = false,
}: {
  card: WalletCard;
  onPress?: () => void;
  compact?: boolean;
  prominent?: boolean;
}) {
  const content = (
    <>
      <CardVisual card={card} />
      <View style={{ flex: 1, gap: compact ? 2 : 5 }}>
        <Copy style={[s.bold, prominent && { fontSize: 18, lineHeight: 25 }]}>
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
        prominent && { minHeight: 96, paddingVertical: 18, gap: 18 },
        pressed && s.pressed,
      ]}
    >
      {content}
    </Pressable>
  ) : (
    <View style={s.cardRow}>{content}</View>
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
    backgroundColor: c.accentSurface,
    borderRadius: 6,
  },
  badgeText: {
    color: c.accent,
    fontSize: 10,
    lineHeight: 17,
    fontWeight: "600",
  },
  buttonDisabled: { opacity: 0.45 },
  button: {
    minHeight: 56,
    borderRadius: 15,
    backgroundColor: c.accent,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    padding: 16,
    gap: 12,
  },
  buttonText: {
    color: c.onAccent,
    fontWeight: "600",
    flexShrink: 1,
    textAlign: "center",
  },
  secondary: { backgroundColor: c.accentSurface },
  pressed: { opacity: 0.65 },
  textAction: {
    minHeight: 44,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 4,
  },
  link: { fontSize: 14, fontWeight: "600", color: c.accent },
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
    borderColor: c.cardDecoration,
    borderWidth: 35,
    right: -100,
    top: -85,
  },
  cardName: {
    color: c.cardInk,
    fontSize: 23,
    lineHeight: 30,
    fontWeight: "500",
    marginTop: 16,
  },
  best: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: c.cardBadge,
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  bestText: { color: c.cardInk, fontSize: 11, lineHeight: 17 },
  cardRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 13,
    paddingVertical: 16,
  },
  stats: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  stat: { flex: 1, minWidth: 70, gap: 4 },
  statBorder: { paddingLeft: 12, borderLeftWidth: 1, borderColor: c.border },
  statValue: {
    fontSize: 22,
    lineHeight: 28,
    fontWeight: "600",
    letterSpacing: -0.8,
  },
  track: { height: 7, borderRadius: 5, backgroundColor: c.track },
  trackFill: { height: 7, borderRadius: 5, backgroundColor: c.accentBright },
  marker: {
    width: 2,
    height: 15,
    position: "absolute",
    top: -4,
    backgroundColor: c.marker,
  },
  bubble: {
    alignSelf: "flex-start",
    maxWidth: "89%",
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.border,
    borderRadius: 17,
    borderBottomLeftRadius: 5,
  },
  userBubble: {
    alignSelf: "flex-end",
    backgroundColor: c.accentSurface,
    borderColor: c.accentSurface,
    borderBottomLeftRadius: 17,
    borderBottomRightRadius: 5,
  },
  modal: { flex: 1, backgroundColor: c.scrim, justifyContent: "flex-end" },
  sheet: {
    backgroundColor: c.elevated,
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
    backgroundColor: c.marker,
    alignSelf: "center",
  },
});
