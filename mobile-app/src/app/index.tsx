import { router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  useWindowDimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  Button,
  CardVisual,
  Copy,
  Icon,
  IconButton,
  Panel,
  Sheet,
  s,
  TextAction,
} from "@/components/creditpick";
import { money } from "@/domain/models";
import type { WalletCard as WalletCardData } from "@/services/contracts";
import { useCreditPick } from "@/state/creditpick-provider";
import { theme } from "@/theme";
import { WalletCard } from "@/components/wallet-card";

export default function HomeScreen() {
  const { wallet, walletError, reloadWallet } = useCreditPick();
  const { fontScale, height, width } = useWindowDimensions();
  const cardWidth = Math.min(Math.min(width, 580) - 64, 360);
  const accessibleScroll = fontScale > 1.2 || height < 920;
  const HomeContainer = accessibleScroll ? ScrollView : View;
  const [selected, setSelected] = useState<WalletCardData | null>(null);
  const [showAddCard, setShowAddCard] = useState(false);
  const cards = wallet?.cards ?? [];
  const profileName = "Alex";
  function openConversation(mode: "type" | "record") {
    router.push({
      pathname: "/conversation",
      params: {
        typing: mode === "type" ? "1" : "0",
        record: mode === "record" ? "1" : "0",
      },
    });
  }
  return (
    <SafeAreaView style={styles.screen}>
      <HomeContainer
        style={{ flex: 1 }}
        scrollEnabled={accessibleScroll}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={accessibleScroll ? { flexGrow: 1 } : { flex: 1 }}
      >
        <View style={[styles.content, accessibleScroll && { flex: 0 }]}>
          <View style={styles.brand}>
            <Copy
              accessibilityRole="header"
              numberOfLines={1}
              adjustsFontSizeToFit
              style={styles.wordmark}
            >
              CreditPick.
            </Copy>
            <View
              accessible
              accessibilityLabel={`${profileName}, profile`}
              style={styles.profile}
            >
              <Copy numberOfLines={1} style={styles.profileName}>
                {profileName}
              </Copy>
              <View style={styles.avatar}>
                <Icon name="user" size={22} color={theme.colors.ink} />
              </View>
            </View>
          </View>
          <View style={styles.intro}>
            <Copy
              numberOfLines={1}
              adjustsFontSizeToFit
              style={styles.heading}
            >
              Choose your next card wisely.
            </Copy>
            <Copy style={styles.supporting}>
              A little clarity before you pay.
            </Copy>
          </View>
          <View style={styles.cardsHeader}>
            <Copy accessibilityRole="header" style={styles.sectionTitle}>
              Your cards
            </Copy>
            <IconButton
              name="plus"
              label="Add a card"
              onPress={() => setShowAddCard(true)}
            />
          </View>
          <View style={styles.cardList}>
            {walletError ? (
              <Panel>
                <Copy accessibilityRole="alert">{walletError}</Copy>
                <TextAction title="Retry" onPress={reloadWallet} />
              </Panel>
            ) : !wallet ? (
              <ActivityIndicator
                color={theme.colors.accent}
                accessibilityLabel="Loading cards"
              />
            ) : (
              <ScrollView
                key={cardWidth}
                horizontal
                showsHorizontalScrollIndicator={false}
                snapToInterval={cardWidth + 14}
                decelerationRate="fast"
                disableIntervalMomentum
                contentContainerStyle={{
                  gap: 14,
                  paddingHorizontal: (Math.min(width, 580) - cardWidth) / 2,
                  paddingTop: 8,
                  paddingBottom: 20,
                  alignItems: "flex-start",
                }}
              >
                {cards.map((card, index) => (
                  <WalletCard
                    key={card.id}
                    card={card}
                    width={cardWidth}
                    index={index}
                    onPress={() => setSelected(card)}
                  />
                ))}
                {!cards.length && (
                  <Copy style={s.small}>No cards to display.</Copy>
                )}
              </ScrollView>
            )}
          </View>
          <Copy style={[s.small, styles.carouselHint]}>
            Swipe left or right · Tap a card for details
          </Copy>
          <View style={{ flex: 1 }} />
          <View style={styles.voiceDock}>
            <Copy style={styles.askTitle}>What are you buying?</Copy>
            <Copy style={styles.supporting}>Tell us the store and amount.</Copy>
            <View style={styles.controls}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Start speaking"
                onPress={() => openConversation("record")}
                style={({ pressed }) => [
                  styles.microphone,
                  pressed && s.pressed,
                ]}
              >
                <Icon name="mic" size={24} color={theme.colors.onAccent} />
                <Copy style={styles.microphoneLabel}>Start speaking</Copy>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="View conversation transcript or type a message"
                onPress={() => openConversation("type")}
                style={({ pressed }) => [styles.chat, pressed && s.pressed]}
              >
                <Icon name="message-circle" size={22} />
                <Copy style={styles.chatLabel}>Type</Copy>
              </Pressable>
            </View>
            <Copy style={[s.small, { textAlign: "center" }]}>
              Tap the mic to start talking · Or use chat to type
            </Copy>
          </View>
        </View>
      </HomeContainer>
      <Sheet
        visible={showAddCard}
        title="Add a card"
        onClose={() => setShowAddCard(false)}
      >
        <Panel style={{ gap: 12 }}>
          <Icon name="credit-card" size={32} />
          <Copy style={s.bold}>Connect your cards here</Copy>
          <Copy>
            Adding a card from the app isn’t wired up yet. Accounts are linked
            by the backend and appear in your carousel once they sync.
          </Copy>
        </Panel>
        <Button title="Got it" onPress={() => setShowAddCard(false)} />
      </Sheet>
      <Sheet
        visible={!!selected}
        title="Card details"
        onClose={() => setSelected(null)}
      >
        {selected && (
          <>
            <CardVisual card={selected} large />
            <Panel style={{ gap: 12 }}>
              <View style={styles.balanceSummary}>
                <Copy style={styles.supporting}>Current balance</Copy>
                <Copy style={styles.balance}>{money(selected.balance)}</Copy>
              </View>
              <Copy>Credit limit: {money(selected.limit)}</Copy>
              <Copy>Available credit: {money(selected.available)}</Copy>
              <Copy>Utilization: {selected.utilization.toFixed(1)}%</Copy>
              <Copy style={s.small}>{selected.rewardSummary}</Copy>
            </Panel>
          </>
        )}
      </Sheet>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.colors.background },
  content: {
    flex: 1,
    width: "100%",
    maxWidth: 580,
    alignSelf: "center",
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  brand: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
    paddingHorizontal: 8,
    paddingTop: 18,
    paddingBottom: 20,
  },
  wordmark: {
    fontFamily: theme.fontFamily,
    fontWeight: "700",
    fontSize: 44,
    lineHeight: 54,
    letterSpacing: -1.5,
    color: theme.colors.ink,
    flexShrink: 1,
  },
  profile: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 10,
    flexShrink: 1,
  },
  profileName: {
    fontSize: 14,
    lineHeight: 20,
    fontWeight: "600",
    color: theme.colors.muted,
    flexShrink: 1,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: theme.radius.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.colors.positiveBackground,
    borderWidth: 2,
    borderColor: theme.colors.surface,
    boxShadow: theme.shadow.soft,
  },
  intro: { gap: 8, paddingHorizontal: 8, paddingTop: 4, paddingBottom: 24 },
  heading: {
    fontSize: 16,
    lineHeight: 24,
    fontWeight: "600",
    letterSpacing: -0.2,
    color: theme.colors.ink,
  },
  supporting: { fontSize: 14, lineHeight: 21, color: theme.colors.muted },
  cardsHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 8,
    paddingBottom: 8,
  },
  sectionTitle: { fontSize: 20, lineHeight: 28, fontWeight: "600" },
  cardList: { flexShrink: 0, marginHorizontal: -16 },
  carouselHint: { paddingHorizontal: 8, textAlign: "center" },
  voiceDock: {
    alignItems: "center",
    marginTop: 24,
    padding: 20,
    gap: 4,
    borderRadius: theme.radius.lg,
    backgroundColor: theme.colors.surface,
    boxShadow: theme.shadow.soft,
  },
  askTitle: { fontSize: 20, lineHeight: 27, fontWeight: "600" },
  controls: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 16,
  },
  microphone: {
    flex: 1,
    minHeight: 64,
    paddingVertical: 16,
    paddingHorizontal: 16,
    gap: 10,
    flexDirection: "row",
    borderRadius: theme.radius.pill,
    backgroundColor: theme.colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  microphoneLabel: {
    flexShrink: 1,
    fontSize: 15,
    lineHeight: 21,
    fontWeight: "600",
    color: theme.colors.onAccent,
    textAlign: "center",
  },
  chat: {
    minWidth: 72,
    minHeight: 64,
    padding: 10,
    gap: 4,
    borderRadius: theme.radius.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.colors.background,
  },
  chatLabel: { fontSize: 12, lineHeight: 16, color: theme.colors.muted },
  balanceSummary: { gap: 4, paddingBottom: 12 },
  balance: {
    fontSize: 40,
    lineHeight: 48,
    fontWeight: "700",
    letterSpacing: -1.5,
    fontVariant: ["tabular-nums"],
  },
});
