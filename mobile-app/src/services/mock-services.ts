import {
  cards,
  comparisonCards,
  estimate,
  initialPurchase,
  rankCards,
  wallet,
} from "../data/demo.ts";
import { money, validateAmount } from "../domain/models.ts";
import type { CardCueServices, CardOption, WalletCard } from "./contracts";
import type { Purchase } from "../domain/models";

export function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new Error("Request cancelled"));
      return;
    }
    const abort = () => {
      clearTimeout(timer);
      reject(new Error("Request cancelled"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal.addEventListener("abort", abort, { once: true });
  });
}
const walletCards: WalletCard[] = cards.map((card) => ({
  ...card,
  rewardSummary:
    card.reward === "points" ? "2× on purchases" : "3% on groceries",
  available: card.limit - card.balance,
  utilization: (card.balance / card.limit) * 100,
}));
function option(card: WalletCard, purchase: Purchase): CardOption {
  const result = estimate(card, purchase);
  return {
    card,
    ...result,
    rewardLabel:
      card.reward === "cashback"
        ? `${money(result.rewards, 2)} cash back`
        : `${result.rewards.toLocaleString()} points`,
    rewardDetail:
      card.reward === "points"
        ? "2× on purchases"
        : `${result.rate}% ${purchase.category === "Groceries" ? "grocery" : "purchase"} rewards`,
  };
}
// Mock business rules stay here. Screens never rank cards or generate speech.
export function createMockServices(
  playback: CardCueServices["playback"],
): CardCueServices {
  return {
    mode: "demo",
    initialPurchase,
    maxPurchaseAmount: 2500,
    wallet: {
      async get(signal) {
        await delay(100, signal);
        return {
          cards: walletCards,
          featuredCardIds: comparisonCards.map((card) => card.id),
          available: wallet.limit - wallet.balance,
          utilization: (wallet.balance / wallet.limit) * 100,
          isDemo: true,
        };
      },
    },
    recommendations: {
      async compare(purchase, threshold, signal) {
        await delay(650, signal);
        const options = rankCards(purchase).map((card) =>
          option(
            walletCards.find((item) => item.id === card.id)!,
            purchase,
          ),
        );
        const best = options[0];
        const belowThreshold = best.utilization < threshold;
        return {
          purchase: { ...purchase },
          best,
          alternatives: options.slice(1),
          belowThreshold,
          threshold,
          isDemo: true,
          reasons: [
            {
              icon: "award",
              title:
                best.card.reward === "cashback"
                  ? "Highest eligible cashback"
                  : "Highest estimated reward value",
              detail:
                best.card.reward === "cashback"
                  ? `${best.rate}% ${purchase.category === "Groceries" ? "at grocery stores" : "on purchases"}`
                  : "2× points · Demo value: 1¢ per point",
            },
            {
              icon: "credit-card",
              title: `${money(best.available, best.available % 1 ? 2 : 0)} available after purchase`,
              detail: `${money(best.card.available)} current → ${money(best.available, best.available % 1 ? 2 : 0)} after`,
            },
            {
              icon: "pie-chart",
              title: `${best.utilization.toFixed(1)}% projected utilization`,
            },
          ],
          voice: {
            transcript: `Demo recommendation: Use ${best.card.name} for your ${money(purchase.amount, 2)} purchase at ${purchase.store}. Earn ${best.rewardLabel}. You would have ${money(best.available, 2)} available and ${best.utilization.toFixed(1)} percent projected utilization, ${belowThreshold ? "below" : "at or above"} your ${threshold} percent alert threshold. These are illustrative estimates.`,
          },
        };
      },
    },
    conversation: {
      async sendText(text, _purchase, signal) {
        await delay(150, signal);
        const amount = validateAmount(text);
        return amount === null
          ? {
              reply:
                "This is a scripted demo. Send an amount like $90, or tap the store and category chips to edit your purchase.",
            }
          : {
              purchasePatch: { amount },
              reply: `Updated your purchase to ${money(amount, amount % 1 ? 2 : 0)}. Ready to compare.`,
            };
      },
    },
    voice: {
      async start(onEvent, signal) {
        if (signal.aborted) throw new Error("Request cancelled");
        onEvent({ type: "status", status: "listening" });
        const timer = setTimeout(() => {
          if (!signal.aborted) onEvent({ type: "status", status: "idle" });
        }, 3200);
        const close = () => {
          clearTimeout(timer);
          signal.removeEventListener("abort", close);
        };
        signal.addEventListener("abort", close, { once: true });
        return {
          close,
          async finish() {
            close();
            onEvent({ type: "status", status: "idle" });
          },
          async sendAudio() {
            throw new Error("Audio capture is disabled in demo mode");
          },
        };
      },
    },
    playback,
  };
}
