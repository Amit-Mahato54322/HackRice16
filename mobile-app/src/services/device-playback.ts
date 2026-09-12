import * as Speech from "expo-speech";
import { createAudioPlayer } from "expo-audio";
import type { CreditPickServices, VoiceOutput } from "./contracts";

type AudioPlayer = ReturnType<typeof createAudioPlayer>;

let currentPlayer: AudioPlayer | null = null;

function releasePlayer() {
  const player = currentPlayer;
  currentPlayer = null;
  if (!player) return;
  try {
    player.pause();
  } catch {
    // already stopped/unloaded
  }
  try {
    player.remove();
  } catch {
    // already released
  }
}

// Plays backend-generated ElevenLabs audio via a real URL/stream.
async function playRemoteAudio(url: string, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return;
  releasePlayer();
  const player = createAudioPlayer(url);
  currentPlayer = player;

  await new Promise<void>((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      subscription.remove();
      signal.removeEventListener("abort", abort);
      releasePlayer();
      resolve();
    };
    const abort = () => finish();
    const subscription = player.addListener("playbackStatusUpdate", (status) => {
      if (status.didJustFinish) finish();
    });
    signal.addEventListener("abort", abort, { once: true });
    player.play();
  });
}

// Demo/no-audio fallback: speaks the transcript via on-device TTS.
async function speakTranscript(transcript: string, signal: AbortSignal): Promise<void> {
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
    Speech.speak(transcript, {
      language: "en-US",
      rate: 0.95,
      onDone: done,
      onStopped: done,
      onError: done,
    });
  });
}

// Plays the backend's generated audio when present (see docs/PLAN.md M8 and
// mobile-app/ARCHITECTURE.md "Voice / ElevenLabs"); falls back to on-device
// speech synthesis of the transcript when it isn't (demo mode, or a backend
// response with no audio attached). The screen always retains the transcript
// if playback of either kind fails.
export const devicePlayback: CreditPickServices["playback"] = {
  async stop() {
    releasePlayer();
    await Speech.stop();
  },
  async play(output: VoiceOutput, signal: AbortSignal) {
    if (output.audio?.url) {
      await playRemoteAudio(output.audio.url, signal);
      return;
    }
    await speakTranscript(output.transcript, signal);
  },
};
