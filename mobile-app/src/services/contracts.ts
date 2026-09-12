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
};
export type ConversationTurn = {
  reply: string;
  purchasePatch?: Partial<Purchase>;
  voice?: VoiceOutput;
  // What the user said, when this turn came from a recorded clip rather
  // than typed text -- absent for sendText() turns.
  transcript?: string;
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
    // A recorded clip's local file URI (not its bytes -- the adapter reads
    // it). Single-shot: no partial results, no follow-up questions.
    sendVoice: (
      fileUri: string,
      mimeType: string,
      purchase: Purchase,
      signal: AbortSignal,
    ) => Promise<ConversationTurn>;
  };
  // Retained for a future streaming capture adapter. The backend has no
  // streaming endpoint, so today's recording flow calls
  // conversation.sendVoice directly instead of going through this.
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
