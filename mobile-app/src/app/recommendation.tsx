import { router, useFocusEffect } from "expo-router";
import { useCallback, useRef, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import {
  Badge,
  Button,
  CardVisual,
  Copy,
  Header,
  Icon,
  IconName,
  Panel,
  Screen,
  Sheet,
  s,
  TextAction,
} from "@/components/creditpick";
import { money } from "@/domain/models";
import { useCreditPick } from "@/state/creditpick-provider";
import { theme } from "@/theme";

export default function RecommendationScreen() {
  const { recommendation, reset, services } = useCreditPick();
  const [comparison, setComparison] = useState(false);
  const [transcript, setTranscript] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const active = useRef(true);
  const playback = useRef<AbortController | null>(null);
  useFocusEffect(
    useCallback(() => {
      active.current = true;
      setSpeaking(false);
      return () => {
        active.current = false;
        playback.current?.abort();
        void services.playback.stop().catch(() => {});
      };
    }, [services]),
  );
  async function hear() {
    if (!recommendation) return;
    setTranscript(true);
    if (speaking) {
      playback.current?.abort();
      await services.playback.stop().catch(() => {});
      setSpeaking(false);
      return;
    }
    try {
      playback.current?.abort();
      const request = new AbortController();
      playback.current = request;
      setSpeaking(true);
      await services.playback.play(recommendation.voice, request.signal);
    } catch {
      // The transcript remains available when playback fails.
    } finally {
      if (active.current) setSpeaking(false);
    }
  }
  if (!recommendation)
    return (
      <Screen>
        <Header title="Your best card" back />
        <Copy>Compare a purchase to get your recommendation.</Copy>
        <Button
          title="Ask CreditPick"
          onPress={() => router.replace("/conversation")}
        />
      </Screen>
    );
  const { purchase, threshold, belowThreshold: below } = recommendation;
  const result = recommendation.best;
  const best = result.card;
  const alternative = recommendation.alternatives[0];
  const other = alternative?.card;
  const reward = result.rewardLabel;
  const explanation = recommendation.voice.transcript;
  return (
    <Screen bottom fit>
      <View style={{ gap: 3 }}>
        <Header title="Your best card" back />
        <Copy style={styles.subtitle}>
          {purchase.store} ·{" "}
          {money(purchase.amount, purchase.amount % 1 ? 2 : 0)} ·{" "}
          {purchase.category}
        </Copy>
      </View>
      <View style={{ gap: 12 }}>
        <CardVisual card={best} large best compact />
        <View style={styles.reward}>
          <View style={styles.rewardIcon}>
            <Icon name="gift" size={22} />
          </View>
          <View style={{ flex: 1, gap: 3 }}>
            <Copy style={styles.rewardTitle}>Earn {reward}</Copy>
            <Copy style={{ color: theme.colors.accent, fontSize: 13 }}>
              {result.rewardDetail}
            </Copy>
          </View>
        </View>
      </View>
      <Panel style={{ padding: 0, overflow: "hidden" }}>
        <View style={{ padding: 12, gap: 8 }}>
          <Copy style={s.sectionTitle}>Why this card</Copy>
          {recommendation.reasons.map((reason) => (
            <Reason key={reason.icon} {...reason} />
          ))}
        </View>
        <View
          style={[
            styles.threshold,
            !below && { backgroundColor: theme.colors.warningBackground },
          ]}
        >
          <Icon
            name={below ? "check-circle" : "alert-circle"}
            size={16}
            color={below ? theme.colors.accent : theme.colors.warning}
          />
          <Copy
            style={[
              styles.thresholdText,
              !below && { color: theme.colors.warning },
            ]}
          >
            {below ? "Below" : "At or above"} your {threshold}% alert threshold
          </Copy>
        </View>
      </Panel>
      {other && alternative && (
        <View style={{ gap: 4 }}>
          <Copy style={s.sectionTitle}>Other option</Copy>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="View comparison"
            onPress={() => setComparison(true)}
          >
            <Panel style={{ padding: 10 }}>
              <View style={s.row}>
                <View style={{ flex: 1, gap: 4 }}>
                  <Copy style={s.bold}>{other.name}</Copy>
                  <Copy style={s.small}>{alternative.rewardDetail}</Copy>
                </View>
                <View style={{ alignItems: "flex-end", flexShrink: 1 }}>
                  <Copy
                    style={{ fontWeight: "600", color: theme.colors.accent }}
                  >
                    {alternative.rewardLabel}
                  </Copy>
                  <Copy style={s.small}>View comparison</Copy>
                </View>
              </View>
            </Panel>
          </Pressable>
        </View>
      )}
      <View style={{ gap: 0 }}>
        <Button
          title={speaking ? "Stop recommendation" : "Hear recommendation"}
          icon={speaking ? "square" : "volume-2"}
          onPress={() => void hear()}
        />
        <TextAction
          title="Ask another question"
          onPress={() => {
            reset();
            router.dismissTo("/conversation");
          }}
        />
        <View style={{ alignItems: "center", gap: 6 }}>
          <Copy style={[s.small, { textAlign: "center" }]}>
            Estimates based on your latest synced balances.
          </Copy>
        </View>
      </View>
      <Sheet
        visible={comparison}
        title="Compare your cards"
        onClose={() => setComparison(false)}
      >
        <Copy style={s.small}>
          {purchase.store} · {money(purchase.amount, 2)}
        </Copy>
        {[result, ...recommendation.alternatives].map((value) => {
          const card = value.card;
          return (
            <Panel
              key={card.id}
              style={{
                gap: 10,
                backgroundColor:
                  card.id === best.id
                    ? theme.colors.accentSurface
                    : theme.colors.surface,
              }}
            >
              <View style={s.row}>
                <Copy style={[s.bold, { flex: 1 }]}>{card.name}</Copy>
                {card.id === best.id && <Badge>Best match</Badge>}
              </View>
              <Copy>
                {card.reward === "points"
                  ? `${value.rewards.toLocaleString()} points (≈ ${money(value.rewardValue, 2)})`
                  : `${money(value.rewards, 2)} cash back`}
              </Copy>
              <Copy style={s.small}>
                {value.available >= 0
                  ? `${money(value.available, 2)} available after purchase`
                  : `Exceeds available credit by ${money(-value.available, 2)}`}
              </Copy>
              <Copy style={s.small}>
                {value.utilization.toFixed(1)}% projected utilization
              </Copy>
            </Panel>
          );
        })}
        <Copy style={s.small}>
          Reward estimates come from each card’s published earn rates.
          Utilization = (balance + purchase) ÷ credit limit. The alert
          threshold is a personal reminder, not a credit-score guarantee.
        </Copy>
        <Button title="Done" onPress={() => setComparison(false)} />
      </Sheet>
      <Sheet
        visible={transcript}
        title="Recommendation"
        onClose={() => setTranscript(false)}
      >
        <Copy>{explanation}</Copy>
        <Button
          title={speaking ? "Stop playback" : "Play again"}
          onPress={() => void hear()}
        />
      </Sheet>
    </Screen>
  );
}
function Reason({
  icon,
  title,
  detail,
}: {
  icon: IconName;
  title: string;
  detail?: string;
}) {
  return (
    <View style={{ flexDirection: "row", gap: 12, alignItems: "flex-start" }}>
      <View style={{ paddingTop: 2 }}>
        <Icon name={icon} size={19} />
      </View>
      <View style={{ flex: 1, gap: 3 }}>
        <Copy style={{ fontSize: 14, lineHeight: 21, fontWeight: "500" }}>
          {title}
        </Copy>
        {detail && <Copy style={s.small}>{detail}</Copy>}
      </View>
    </View>
  );
}
const styles = StyleSheet.create({
  subtitle: { fontSize: 13, color: theme.colors.muted, marginLeft: 12 },
  reward: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 10,
    borderRadius: 16,
    backgroundColor: theme.colors.accentSurface,
  },
  rewardIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: theme.colors.accentSurfaceStrong,
    alignItems: "center",
    justifyContent: "center",
  },
  rewardTitle: {
    fontSize: 20,
    lineHeight: 27,
    fontWeight: "600",
    color: theme.colors.accent,
    letterSpacing: -0.4,
  },
  threshold: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: theme.colors.accentSurface,
    paddingHorizontal: 20,
    paddingVertical: 8,
  },
  thresholdText: {
    fontSize: 12,
    lineHeight: 18,
    color: theme.colors.accent,
    flex: 1,
  },
});
