import * as Speech from "expo-speech";
import type { CardCueServices } from "./contracts";

// Replace this adapter with native URL playback when the backend returns audio.
// The screen always retains the transcript if playback is unavailable.
export const devicePlayback: CardCueServices["playback"] = {
  stop: () => Speech.stop(),
  async play(output, signal) {
    if (signal.aborted) return;
    const voices = await Speech.getAvailableVoicesAsync();
    if (signal.aborted || !voices.length) return;
    await Speech.stop();
    if (signal.aborted) return;
    await new Promise<void>((resolve) => {
      const done = () => {
        signal.removeEventListener("abort", abort);
        resolve();
      };
      const abort = () => {
        void Speech.stop().catch(() => {});
        done();
      };
      signal.addEventListener("abort", abort, { once: true });
      Speech.speak(output.transcript, {
        language: "en-US",
        rate: 0.95,
        onDone: done,
        onStopped: done,
        onError: done,
      });
    });
  },
};
