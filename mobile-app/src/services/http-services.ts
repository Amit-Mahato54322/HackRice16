import { Platform } from "react-native";
import { money } from "../domain/models.ts";
import type { Category, Purchase } from "../domain/models";
import { cardArt } from "../components/card-art";
import type {
  CardOption,
  CreditPickServices,
  Recommendation,
  VoiceOutput,
  WalletCard,
  WalletSnapshot,
} from "./contracts";

// The FastAPI host. Expo inlines EXPO_PUBLIC_* at build time; on a phone this
// must be the laptop's LAN address, not localhost.
const BASE_URL = (
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

const REQUEST_TIMEOUT_MS = 15_000;
// /conversation and /conversation/voice can chain up to three sequential
// Gemini calls server-side (transcribe, translate, and a second translate
// after a purchase patch -- see backend/app/routers/conversation.py), each
// with its own multi-attempt retry budget. The flat 15s default was tuned
// for single-call endpoints and cuts these off before the backend is done,
// showing a false "failed" while it's still working.
const CONVERSATION_TIMEOUT_MS = 45_000;

/** Frontend categories are display strings; the engine's are lowercase keys. */
const TO_ENGINE: Record<Category, string> = {
  Groceries: "groceries",
  Dining: "dining",
  Travel: "travel",
  Other: "other",
};

/** The engine knows more categories than the UI can name. */
const FROM_ENGINE: Record<string, Category> = {
  groceries: "Groceries",
  dining: "Dining",
  travel: "Travel",
};

function toCategory(value: string | undefined): Category {
  return (value && FROM_ENGINE[value.toLowerCase()]) || "Other";
}

async function request<T>(
  path: string,
  signal: AbortSignal,
  init?: RequestInit,
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<T> {
  // Fail fast rather than hang: a phone pointed at an unreachable laptop
  // otherwise spins until the user gives up.
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), timeoutMs);
  const abort = () => timeout.abort();
  signal.addEventListener("abort", abort, { once: true });

  try {
    // FormData (voice upload) must not get a manual Content-Type -- fetch
    // sets its own multipart boundary, which a fixed header would break.
    const isFormData = init?.body instanceof FormData;
    const response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: timeout.signal,
      headers: isFormData
        ? init?.headers
        : { "Content-Type": "application/json", ...init?.headers },
    });
    if (!response.ok) {
      // A raised HTTPException gives {"detail": "..."}; FastAPI's own request
      // validation (missing/malformed field) gives {"detail": [{loc, msg}]}
      // instead -- surface either rather than a bare status code, which told
      // us nothing about what actually failed.
      const reason = await response
        .json()
        .then((body) => {
          if (typeof body?.detail === "string") return body.detail;
          if (Array.isArray(body?.detail)) {
            return body.detail
              .map((e: { loc?: unknown[]; msg?: string }) =>
                e.msg ? `${e.loc?.join(".") ?? "field"}: ${e.msg}` : null,
              )
              .filter(Boolean)
              .join("; ");
          }
          return undefined;
        })
        .catch(() => undefined);
      throw new Error(
        reason || `${init?.method ?? "GET"} ${path} failed: ${response.status}`,
      );
    }
    return (await response.json()) as T;
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", abort);
  }
}

// --- wire types -------------------------------------------------------------

type DashboardCard = {
  id: number;
  vectormint_card_id?: string | null;
  card_art_url?: string | null;
  nessie_account_id: string;
  official_name: string;
  credit_limit: number;
  current_balance: number;
  amount_remaining: number;
  utilization_pct: number;
  is_configured: boolean;
  card_display_name: string | null;
  card_issuer: string | null;
};

type ScoredCard = {
  card_id: string;
  display_name: string;
  reward_rate: number;
  estimated_value: number;
  score: number;
  why: string;
  // Reported by the engine because the client cannot derive it: /recommend may
  // score a wallet whose cards are not the accounts /dashboard lists.
  credit_limit?: number | null;
  current_balance?: number | null;
  available?: number | null;
  utilization?: number | null;
};

type RecommendResponse = {
  category: string;
  recommendation: ScoredCard | null;
  ranked: ScoredCard[];
  disqualified: { card?: string; card_name?: string; reason: string }[];
  voice: { transcript: string; audio?: { url: string; mimeType: string } };
};

type ConversationResponse = {
  reply: string;
  purchasePatch?: { store?: string; amount?: number } | null;
  voice?: { transcript: string; audio?: { url: string; mimeType: string } };
  // Only /conversation/voice sets this: what Gemini heard the user say.
  transcript?: string;
};

// --- mapping ----------------------------------------------------------------

/** The backend serves clips from /static, relative to the API host; expo-audio
 * needs an absolute URL. Shared by /recommend and /conversation's voice. */
function toAbsoluteVoice(voice: VoiceOutput): VoiceOutput {
  return {
    ...voice,
    audio: voice.audio
      ? {
          ...voice.audio,
          url: voice.audio.url.startsWith("http")
            ? voice.audio.url
            : `${BASE_URL}${voice.audio.url}`,
        }
      : undefined,
  };
}

function toWalletCard(card: DashboardCard, index: number): WalletCard {
  const limit = card.credit_limit || 0;
  return {
    id: String(card.id),
    name: card.card_display_name ?? card.official_name,
    // The dashboard exposes no card number; the Nessie account id is the only
    // stable identifier, so its tail stands in for the printed digits.
    digits: card.nessie_account_id.slice(-4),
    limit,
    balance: card.current_balance ?? 0,
    reward: "cashback",
    // The issuer's own palette, so a Chase card reads as a Chase card.
    color: cardArt(
      card.vectormint_card_id ?? undefined,
      card.card_issuer ?? undefined,
      index,
    ).background,
    rewardSummary: card.card_display_name
      ? `${card.card_issuer ?? "Card"} rewards`
      : "Not configured",
    available: card.amount_remaining ?? 0,
    utilization: card.utilization_pct ?? 0,
    productId: card.vectormint_card_id ?? undefined,
    issuer: card.card_issuer ?? undefined,
    artUrl: card.card_art_url ?? undefined,
  };
}

/** A card the engine scored but the dashboard does not list. */
function placeholderCard(scored: ScoredCard, index: number): WalletCard {
  const limit = scored.credit_limit ?? 0;
  const balance = scored.current_balance ?? 0;
  return {
    id: scored.card_id,
    name: scored.display_name,
    digits: "----",
    limit,
    balance,
    reward: "cashback",
    color: cardArt(scored.card_id, undefined, index).background,
    rewardSummary: scored.why,
    available: limit - balance,
    utilization: limit ? (balance / limit) * 100 : 0,
  };
}

function toOption(
  scored: ScoredCard,
  wallet: Map<string, WalletCard>,
  purchase: Purchase,
  index: number,
): CardOption {
  const card = wallet.get(scored.card_id) ?? placeholderCard(scored, index);
  // Prefer the engine's own figures; they describe the wallet it actually
  // scored. Fall back to the dashboard card only if the backend omits them.
  const available =
    scored.available ??
    Math.round((card.limit - card.balance - purchase.amount) * 100) / 100;
  const utilization =
    scored.utilization != null
      ? scored.utilization * 100
      : card.limit
        ? ((card.balance + purchase.amount) / card.limit) * 100
        : 0;

  return {
    card,
    rate: Math.round(scored.reward_rate * 1000) / 10,
    rewards: scored.estimated_value,
    rewardValue: scored.estimated_value,
    available,
    utilization,
    rewardLabel: `${money(scored.estimated_value, 2)} cash back`,
    rewardDetail: scored.why,
  };
}

function toRecommendation(
  body: RecommendResponse,
  wallet: Map<string, WalletCard>,
  purchase: Purchase,
  threshold: number,
): Recommendation {
  const scored = body.recommendation
    ? [body.recommendation, ...body.ranked]
    : [];
  if (!scored.length) {
    const refused = body.disqualified
      .map((item) => `${item.card_name ?? "A card"}: ${item.reason}`)
      .join(". ");
    throw new Error(
      refused
        ? `No card can cover this purchase. ${refused}`
        : "No card can cover this purchase.",
    );
  }

  const options = scored.map((card, index) =>
    toOption(card, wallet, purchase, index),
  );
  const best = options[0];

  return {
    purchase: { ...purchase, category: toCategory(body.category) },
    best,
    alternatives: options.slice(1),
    // A client-side alert, compared against the same projected utilization
    // shown on screen.
    belowThreshold: best.utilization < threshold,
    threshold,
    reasons: [
      {
        icon: "award",
        title: `Earn ${best.rewardLabel}`,
        detail: best.rewardDetail,
      },
      {
        icon: "credit-card",
        title: `${money(best.available, best.available % 1 ? 2 : 0)} available after purchase`,
        detail: `${money(best.card.available)} current → ${money(best.available, best.available % 1 ? 2 : 0)} after`,
      },
      {
        icon: "pie-chart",
        title: `${best.utilization.toFixed(1)}% projected utilization`,
        // Cards the engine refused outright, so they do not vanish silently.
        detail: body.disqualified.length
          ? `${body.disqualified.length} card${body.disqualified.length > 1 ? "s" : ""} skipped: ${body.disqualified[0].reason}`
          : undefined,
      },
    ],
    voice: toAbsoluteVoice(body.voice),
  };
}

// --- services ---------------------------------------------------------------

export function createHttpServices(
  playback: CreditPickServices["playback"],
): CreditPickServices {
  // Populated by wallet.get and read by recommendations.compare, which
  // receives card ids the dashboard has already described.
  let walletCards = new Map<string, WalletCard>();

  return {
    // Empty on purpose: the user says what they are buying. Nothing is
    // pre-filled, so no figure on screen was invented by us.
    initialPurchase: { store: "", category: "Other", amount: 0 },
    maxPurchaseAmount: 2500,

    wallet: {
      async get(signal) {
        const body = await request<{ cards: DashboardCard[] }>(
          "/dashboard",
          signal,
        );
        const cards = body.cards.map(toWalletCard);
        walletCards = new Map(cards.map((card) => [card.id, card]));

        const totals = cards.reduce(
          (sum, card) => ({
            limit: sum.limit + card.limit,
            balance: sum.balance + card.balance,
          }),
          { limit: 0, balance: 0 },
        );

        return {
          cards,
          featuredCardIds: cards.slice(0, 2).map((card) => card.id),
          available: totals.limit - totals.balance,
          utilization: totals.limit ? (totals.balance / totals.limit) * 100 : 0,
        } satisfies WalletSnapshot;
      },
    },

    recommendations: {
      async compare(purchase, threshold, signal) {
        const body = await request<RecommendResponse>("/recommend", signal, {
          method: "POST",
          body: JSON.stringify({
            merchant: purchase.store,
            amount: purchase.amount,
            category: TO_ENGINE[purchase.category],
          }),
        });
        return toRecommendation(body, walletCards, purchase, threshold);
      },
    },

    conversation: {
      // The backend runs the engine, then has Gemini phrase the result. Any
      // figure the engine did not compute is rejected server-side, so a reply
      // is either grounded or plainer -- never invented.
      async sendText(text, purchase, signal) {
        const body = await request<ConversationResponse>(
          "/conversation",
          signal,
          {
            method: "POST",
            body: JSON.stringify({
              message: text,
              purchase: {
                store: purchase.store,
                amount: purchase.amount,
                category: TO_ENGINE[purchase.category],
              },
            }),
          },
          CONVERSATION_TIMEOUT_MS,
        );
        return {
          reply: body.reply,
          purchasePatch: body.purchasePatch ?? undefined,
          voice: body.voice ? toAbsoluteVoice(body.voice) : undefined,
        };
      },

      // Single-shot: no history sent, matching the backend's non-goal of
      // multi-turn voice dialogue. The current purchase still travels along
      // as form fields so an earlier typed/edited amount or store isn't lost.
      async sendVoice(fileUri, mimeType, purchase, signal) {
        const form = new FormData();
        if (Platform.OS === "web") {
          // On web the recorder hands back a blob: URL, and the browser's
          // real FormData needs an actual Blob -- the {uri, type, name}
          // object below is a React Native-only convention that a browser
          // silently stringifies into garbage instead of a file part.
          const blob = await fetch(fileUri).then((r) => r.blob());
          const type = blob.type || mimeType;
          form.append("audio", blob, `clip.${type.split("/")[1] ?? "webm"}`);
        } else {
          // React Native's fetch accepts this {uri, type, name} shape in
          // place of a real Blob -- it streams the file at `uri` directly.
          form.append("audio", {
            uri: fileUri,
            type: mimeType,
            name: `clip.${mimeType.split("/")[1] ?? "m4a"}`,
          } as unknown as Blob);
        }
        form.append("store", purchase.store);
        form.append("amount", String(purchase.amount));
        form.append("category", TO_ENGINE[purchase.category]);

        const body = await request<ConversationResponse>(
          "/conversation/voice",
          signal,
          { method: "POST", body: form },
          CONVERSATION_TIMEOUT_MS,
        );
        return {
          reply: body.reply,
          purchasePatch: body.purchasePatch ?? undefined,
          voice: body.voice ? toAbsoluteVoice(body.voice) : undefined,
          transcript: body.transcript,
        };
      },
    },

    voice: {
      // Audio capture needs a streaming endpoint the backend does not have.
      async start(onEvent, signal) {
        if (signal.aborted) throw new Error("Request cancelled");
        onEvent({ type: "status", status: "idle" });
        onEvent({
          type: "error",
          message: "Voice input isn't connected yet. You can type instead.",
        });
        return {
          close() {},
          async finish() {},
          async sendAudio() {
            throw new Error("Voice capture is not available");
          },
        };
      },
    },

    playback,
  };
}
