import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { View } from "react-native";
import { theme } from "@/theme";
import {
  Badge,
  CardRow,
  CardVisual,
  Copy,
  Header,
  Panel,
  Screen,
  Sheet,
  s,
  WalletSummary,
} from "@/components/creditpick";
import { money } from "@/domain/models";
import type { WalletCard } from "@/services/contracts";
import { useCreditPick } from "@/state/creditpick-provider";

export default function WalletScreen() {
  const params = useLocalSearchParams<{ card?: string }>();
  const { wallet } = useCreditPick();
  const cards = wallet?.cards ?? [];
  const [selected, setSelected] = useState<WalletCard | null>(null);
  useEffect(() => {
    if (params.card)
      setSelected(cards.find((card) => card.id === params.card) ?? null);
  }, [params.card, wallet]);
  return (
    <Screen>
      <Header title="Your wallet" />
      <WalletSummary />
      <View style={{ gap: 4 }}>
        <Copy style={s.sectionTitle}>All {cards.length} demo cards</Copy>
        <Copy style={s.small}>
          Local sample balances. No bank accounts connected.
        </Copy>
      </View>
      <View>
        {cards.map((card) => (
          <View
            key={card.id}
            style={{
              borderBottomWidth: 1,
              borderBottomColor: theme.colors.border,
            }}
          >
            <CardRow card={card} onPress={() => setSelected(card)} />
          </View>
        ))}
      </View>
      <Sheet
        visible={!!selected}
        title="Card details"
        onClose={() => {
          setSelected(null);
          router.setParams({ card: undefined });
        }}
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
            </Panel>
            <Copy style={s.small}>
              {["everyday", "travel"].includes(selected.id)
                ? "Included in the purchase comparison demo."
                : "Shown for the wallet summary. The purchase demo compares Everyday Cash and Travel Plus."}
            </Copy>
          </>
        )}
      </Sheet>
    </Screen>
  );
}
