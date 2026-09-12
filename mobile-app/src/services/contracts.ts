import type { CreditCard, Purchase } from "../domain/models";

// Provider-neutral DTOs. A backend adapter maps its wire format into these types.
// Monetary values use USD major units at this boundary; convert integer cents here.
export type WalletCard = CreditCard & {
  rewardSummary: string;
  available: number;
  utilization: number;
};
export type WalletSnapshot = {
  cards: WalletCard[];
  featuredCardIds: string[];
  available: number;
  utilization: number;
  isDemo: boolean;
};
export type CardOption = {
  card: WalletCard;
  rate: number;
  rewards: number;
  rewardValue: number;
  available: number;
  utilization: number;
  rewardLabel: string;
  rewardDetail: string;
};
export type VoiceOutput = {
  transcript: string;
  // Future backend-generated ElevenLabs audio; never a vendor API key.
  audio?: { url: string; mimeType: string };
};
export type Recommendation = {
  purchase: Purchase;
  best: CardOption;
  alternatives: CardOption[];
  belowThreshold: boolean;
  threshold: number;
  reasons: {
    icon: "award" | "credit-card" | "pie-chart";
    title: string;
    detail?: string;
  }[];
  voice: VoiceOutput;
  isDemo: boolean;
};
export type ConversationTurn = {
  reply: string;
  purchasePatch?: Partial<Purchase>;
};
export type VoiceEvent =
  | {
      type: "status";
      status: "connecting" | "listening" | "processing" | "idle";
    }
  | { type: "turn"; turn: ConversationTurn }
  | { type: "error"; message: string };
export type AudioChunk = {
  bytes: Uint8Array;
  mimeType: string;
  sequence: number;
};
export type VoiceSession = {
  sendAudio: (chunk: AudioChunk) => Promise<void>;
  finish: () => Promise<void>;
  close: () => void;
};
export interface CreditPickServices {
  mode: "demo" | "live";
  initialPurchase: Purchase;
  maxPurchaseAmount: number;
  wallet: { get: (signal: AbortSignal) => Promise<WalletSnapshot> };
  recommendations: {
    compare: (
      purchase: Purchase,
      threshold: number,
      signal: AbortSignal,
    ) => Promise<Recommendation>;
  };
  conversation: {
    sendText: (
      text: string,
      purchase: Purchase,
      signal: AbortSignal,
    ) => Promise<ConversationTurn>;
  };
  // The future native audio adapter captures PCM and sends it to our backend.
  // The backend owns ElevenLabs credentials, session creation and processing.
  voice: {
    start: (
      onEvent: (event: VoiceEvent) => void,
      signal: AbortSignal,
    ) => Promise<VoiceSession>;
  };
  playback: {
    play: (output: VoiceOutput, signal: AbortSignal) => Promise<void>;
    stop: () => Promise<void>;
  };
}
