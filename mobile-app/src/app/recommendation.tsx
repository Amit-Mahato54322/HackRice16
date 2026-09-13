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
    <Screen bottom>
      <View style={{ gap: 6 }}>
        <Header title="Your best card" back />
        <Copy style={styles.subtitle}>
          {purchase.store} ·{" "}
          {money(purchase.amount, purchase.amount % 1 ? 2 : 0)} ·{" "}
          {purchase.category}
        </Copy>
      </View>
      <View style={{ gap: 16 }}>
        <CardVisual card={best} large best compact />
        <View style={styles.reward}>
          <View style={styles.rewardIcon}>
            <Icon name="gift" size={22} />
          </View>
          <View style={{ flex: 1, gap: 3 }}>
            <Copy style={styles.rewardTitle}>Earn {reward}</Copy>
            <Copy style={styles.rewardDetail}>{result.rewardDetail}</Copy>
          </View>
        </View>
      </View>
      <Panel style={{ padding: 0, overflow: "hidden" }}>
        <View style={{ padding: 20, gap: 18 }}>
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
            color={below ? theme.colors.positive : theme.colors.warning}
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
        <View style={{ gap: 10 }}>
          <Copy style={s.sectionTitle}>Other option</Copy>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="View comparison"
            onPress={() => setComparison(true)}
          >
            <Panel style={{ padding: 18 }}>
              <View style={s.row}>
                <View style={{ flex: 1, gap: 4 }}>
                  <Copy style={s.bold}>{other.name}</Copy>
                  <Copy style={s.small}>{alternative.rewardDetail}</Copy>
                </View>
                <View style={{ alignItems: "flex-end", flexShrink: 1 }}>
                  <Copy style={styles.alternativeReward}>
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
              <Copy style={styles.comparisonReward}>
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
          Utilization = (balance + purchase) ÷ credit limit. The alert threshold
          is a personal reminder, not a credit-score guarantee.
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
      <View style={styles.reasonIcon}>
        <Icon name={icon} size={19} color={theme.colors.muted} />
      </View>
      <View style={{ flex: 1, gap: 3 }}>
        <Copy style={{ fontSize: 15, lineHeight: 22, fontWeight: "500" }}>
          {title}
        </Copy>
        {detail && <Copy style={s.small}>{detail}</Copy>}
      </View>
    </View>
  );
}
const styles = StyleSheet.create({
  subtitle: {
    fontSize: 13,
    lineHeight: 20,
    color: theme.colors.muted,
    marginLeft: 12,
  },
  // A gain, so it takes the positive pair: pastel ground, darker ink.
  reward: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    padding: 20,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.positiveBackground,
  },
  rewardIcon: {
    width: 48,
    height: 48,
    borderRadius: 16,
    backgroundColor: theme.colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  rewardTitle: {
    fontSize: 28,
    lineHeight: 35,
    fontWeight: "700",
    color: theme.colors.ink,
    letterSpacing: -0.8,
  },
  rewardDetail: {
    color: theme.colors.positive,
    fontSize: 13,
    lineHeight: 20,
  },
  alternativeReward: {
    fontSize: 18,
    lineHeight: 25,
    fontWeight: "600",
    color: theme.colors.ink,
    letterSpacing: -0.4,
  },
  comparisonReward: {
    fontSize: 22,
    lineHeight: 30,
    fontWeight: "600",
    letterSpacing: -0.5,
  },
  reasonIcon: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: theme.colors.accentSurface,
  },
  // Below the threshold is the good outcome, so this footer defaults to the
  // positive pair; the screen swaps both ground and ink to the negative pair
  // when it is at or above.
  threshold: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: theme.colors.positiveBackground,
    paddingHorizontal: 20,
    paddingVertical: 14,
  },
  thresholdText: {
    fontSize: 12,
    lineHeight: 18,
    color: theme.colors.positive,
    flex: 1,
  },
});
