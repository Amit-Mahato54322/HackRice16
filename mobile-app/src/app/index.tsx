import { router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  useWindowDimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  Badge,
  CardRow,
  CardVisual,
  Copy,
  Icon,
  Panel,
  Sheet,
  s,
  TextAction,
} from "@/components/creditpick";
import { money } from "@/domain/models";
import type { WalletCard } from "@/services/contracts";
import { useCreditPick } from "@/state/creditpick-provider";
import { theme } from "@/theme";

export default function HomeScreen() {
  const { wallet, walletError, reloadWallet } = useCreditPick();
  const { fontScale, height } = useWindowDimensions();
  const accessibleScroll = fontScale > 1.2 || height < 650;
  const HomeContainer = accessibleScroll ? ScrollView : View;
  const [expanded, setExpanded] = useState(false);
  const [selected, setSelected] = useState<WalletCard | null>(null);
  const cards =
    wallet?.cards.filter(
      (card) => expanded || wallet.featuredCardIds.includes(card.id),
    ) ?? [];
  function openConversation(typing: boolean) {
    router.push({
      pathname: "/conversation",
      params: { typing: typing ? "1" : "0" },
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
            <Copy accessibilityRole="header" style={styles.wordmark}>
              CreditPick<Copy style={styles.brandDot}>.</Copy>
            </Copy>
          </View>
          <View style={styles.intro}>
            <Copy style={styles.heading}>
              Choose your next{"\n"}card wisely.
            </Copy>
            <Copy style={styles.supporting}>
              A little clarity before you pay.
            </Copy>
          </View>
          <View style={styles.cardsHeader}>
            <Copy accessibilityRole="header" style={styles.sectionTitle}>
              Your cards
            </Copy>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={
                expanded ? "Show featured cards" : "View all cards on Home"
              }
              accessibilityState={{ expanded }}
              onPress={() => setExpanded((value) => !value)}
              style={s.textAction}
            >
              <Copy style={s.link}>{expanded ? "Show less" : "View all"}</Copy>
            </Pressable>
          </View>
          <View
            style={[
              styles.cardList,
              accessibleScroll && { flex: 0, height: expanded ? 420 : 230 },
            ]}
          >
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
            ) : accessibleScroll ? (
              <ScrollView
                nestedScrollEnabled
                contentContainerStyle={{ paddingHorizontal: 14 }}
              >
                {cards.map((card, index) => (
                  <View key={card.id}>
                    {index > 0 && <View style={styles.separator} />}
                    <CardRow
                      card={card}
                      prominent
                      onPress={() => setSelected(card)}
                    />
                  </View>
                ))}
                {!cards.length && (
                  <Copy style={s.small}>No cards to display.</Copy>
                )}
              </ScrollView>
            ) : (
              <FlatList
                nestedScrollEnabled
                data={cards}
                keyExtractor={(card) => card.id}
                showsVerticalScrollIndicator={expanded}
                contentContainerStyle={{ paddingHorizontal: 14 }}
                renderItem={({ item }) => (
                  <CardRow
                    card={item}
                    prominent
                    onPress={() => setSelected(item)}
                  />
                )}
                ItemSeparatorComponent={() => <View style={styles.separator} />}
                ListEmptyComponent={
                  <Copy style={s.small}>No cards to display.</Copy>
                }
              />
            )}
          </View>
          <View style={styles.voiceDock}>
            <Copy style={styles.askTitle}>What are you buying?</Copy>
            <Copy style={styles.supporting}>Tell us the store and amount.</Copy>
            <View style={styles.controls}>
              <View style={styles.sideSlot} />
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Start simulated voice conversation"
                onPress={() => openConversation(false)}
                style={({ pressed }) => [
                  styles.microphone,
                  pressed && s.pressed,
                ]}
              >
                <Icon name="mic" size={34} color={theme.colors.onAccent} />
              </Pressable>
              <View style={styles.sideSlot}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="View conversation transcript or type a message"
                  onPress={() => openConversation(true)}
                  style={({ pressed }) => [styles.chat, pressed && s.pressed]}
                >
                  <Icon name="message-circle" size={25} />
                </Pressable>
              </View>
            </View>
            <Copy style={[s.small, { textAlign: "center" }]}>
              Demo data · Voice is simulated
            </Copy>
          </View>
        </View>
      </HomeContainer>
      <Sheet
        visible={!!selected}
        title="Card details"
        onClose={() => setSelected(null)}
      >
        {selected && (
          <>
            <CardVisual card={selected} large />
            <Badge>Demo data</Badge>
            <Panel style={{ gap: 12 }}>
              <Copy>Credit limit: {money(selected.limit)}</Copy>
              <Copy>Current balance: {money(selected.balance)}</Copy>
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
    paddingBottom: 8,
  },
  brand: { alignItems: "center", paddingVertical: 12 },
  wordmark: {
    fontFamily: Platform.select({
      ios: "Georgia",
      android: "serif",
      default: "Georgia",
    }),
    fontStyle: "italic",
    fontWeight: "700",
    fontSize: 39,
    lineHeight: 49,
    letterSpacing: -1.6,
    color: theme.colors.ink,
    textAlign: "center",
  },
  brandDot: { fontSize: 39, lineHeight: 49, color: theme.colors.accent },
  intro: { gap: 6, paddingHorizontal: 8, paddingTop: 12, paddingBottom: 20 },
  heading: {
    fontSize: 30,
    lineHeight: 36,
    fontWeight: "600",
    letterSpacing: -0.9,
  },
  supporting: { fontSize: 14, lineHeight: 21, color: theme.colors.muted },
  cardsHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 8,
    paddingBottom: 6,
  },
  sectionTitle: { fontSize: 23, lineHeight: 30, fontWeight: "600" },
  cardList: {
    flex: 1,
    minHeight: 100,
    backgroundColor: theme.colors.surface,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: theme.colors.border,
    overflow: "hidden",
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: theme.colors.border,
  },
  voiceDock: { alignItems: "center", paddingTop: 20, gap: 4 },
  askTitle: { fontSize: 20, lineHeight: 27, fontWeight: "600" },
  controls: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 20,
    paddingVertical: 12,
  },
  sideSlot: { width: 54, alignItems: "center" },
  microphone: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: theme.colors.accent,
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0px 6px 20px #00000040",
  },
  chat: {
    width: 54,
    height: 54,
    borderRadius: 27,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.colors.accentSurface,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
});
