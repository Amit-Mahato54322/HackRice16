import { router, useLocalSearchParams, useFocusEffect } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  ActivityIndicator,
  Animated,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
} from "expo-audio";
import {
  Button,
  ChatBubble,
  Copy,
  Header,
  Icon,
  IconButton,
  s,
  TextAction,
} from "@/components/creditpick";
import { categories, money, Purchase, validateAmount } from "@/domain/models";
import { useCreditPick } from "@/state/creditpick-provider";
import { theme } from "@/theme";

// The backend chains several sequential calls for a voice turn (see
// backend/app/routers/conversation.py: transcribe -> translate -> validate ->
// ElevenLabs), which is why it takes 5-10s with nothing to look at. These
// cycle on a timer -- there's no real progress signal from a single HTTP
// response, just an honest guess at which step is likeliest to be running.
const VOICE_STAGES = [
  "Transcribing your recording…",
  "Talking to Gemini…",
  "Checking the numbers…",
  "Generating your voice reply…",
];
const TEXT_STAGES = [
  "Talking to Gemini…",
  "Checking the numbers…",
  "Generating your voice reply…",
];
const STAGE_INTERVAL_MS = 1600;

export default function ConversationScreen() {
  const { typing, record } = useLocalSearchParams<{
    typing?: string;
    record?: string;
  }>();
  const {
    purchase,
    conversationMessages,
    appendMessages,
    flowId,
    updatePurchase,
    services,
    reset,
    compare: requestComparison,
  } = useCreditPick();
  const ready = !!purchase.store.trim() && purchase.amount > 0;
  const [listening, setListening] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [editing, setEditing] = useState<keyof Purchase | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const composer = useRef<TextInput>(null);
  const scroll = useRef<ScrollView>(null);
  const request = useRef<AbortController | null>(null);
  const messageRequest = useRef<AbortController | null>(null);
  const playbackRequest = useRef<AbortController | null>(null);
  const [sending, setSending] = useState(false);
  const [pendingKind, setPendingKind] = useState<"voice" | "text" | null>(
    null,
  );
  const [stageIndex, setStageIndex] = useState(0);
  const wave = useRef(new Animated.Value(0)).current;
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  // Guards the async gap between tapping the mic and the recorder actually
  // starting, so a fast double-tap can't call recorder.record() twice.
  const startingRecording = useRef(false);

  // Leaving mid-recording (back navigation, a message sent instead, "Compare
  // my cards" tapped while listening) must stop the native mic session, not
  // just the `listening` flag -- otherwise it keeps capturing in the
  // background after the screen's moved on.
  const abandonRecording = useCallback(() => {
    setListening((was) => {
      if (was) void recorder.stop().catch(() => {});
      return false;
    });
  }, [recorder]);

  useFocusEffect(
    useCallback(() => {
      setLoading(false);
      setSending(false);
      return () => {
        request.current?.abort();
        messageRequest.current?.abort();
        playbackRequest.current?.abort();
        void services.playback.stop().catch(() => {});
        abandonRecording();
      };
    }, [services, abandonRecording]),
  );
  useEffect(() => {
    request.current?.abort();
    messageRequest.current?.abort();
    playbackRequest.current?.abort();
    void services.playback.stop().catch(() => {});
    setMessage("");
    setReply("");
    setEditing(null);
    setError("");
    setLoading(false);
    setSending(false);
    abandonRecording();
  }, [flowId, typing, services, abandonRecording]);
  useEffect(() => {
    if (typing !== "1") return;
    const focus = setTimeout(() => composer.current?.focus(), 350);
    return () => clearTimeout(focus);
  }, [typing]);
  // Tapping the mic on the home screen should start listening immediately
  // instead of landing here and requiring a second tap.
  useEffect(() => {
    if (record !== "1") return;
    const start = setTimeout(() => void toggleRecording(), 350);
    return () => clearTimeout(start);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record]);
  // Neither backend call reports progress -- this just cycles an honest
  // guess at which sequential step (see VOICE_STAGES above) is likeliest to
  // be running, so the wait isn't a blank screen.
  useEffect(() => {
    if (!sending || !pendingKind) {
      setStageIndex(0);
      return;
    }
    setStageIndex(0);
    const stages = pendingKind === "voice" ? VOICE_STAGES : TEXT_STAGES;
    const id = setInterval(() => {
      setStageIndex((index) => Math.min(index + 1, stages.length - 1));
    }, STAGE_INTERVAL_MS);
    return () => clearInterval(id);
  }, [sending, pendingKind]);
  // `listening` means "actively recording" -- the wave animation runs for as
  // long as capture is on; actually reading the microphone happens in
  // toggleRecording below, not here, since starting/stopping the recorder
  // itself must stay outside a cleanup-driven effect.
  useEffect(() => {
    if (!listening) return;
    let active = true;
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(wave, {
          toValue: 1,
          duration: 450,
          useNativeDriver: true,
        }),
        Animated.timing(wave, {
          toValue: 0,
          duration: 450,
          useNativeDriver: true,
        }),
      ]),
    );
    void AccessibilityInfo.isReduceMotionEnabled().then((reduced) => {
      if (active && !reduced) animation.start();
    });
    return () => {
      active = false;
      animation.stop();
      wave.setValue(0);
    };
  }, [listening, wave]);

  function edit(field: keyof Purchase) {
    setEditing(field);
    setDraft(String(purchase[field]));
    setError("");
  }
  function save() {
    if (editing === "amount") {
      const amount = validateAmount(draft, services.maxPurchaseAmount);
      if (amount === null) {
        setError(
          `Enter an amount from $0.01 to ${money(services.maxPurchaseAmount)}, with up to two decimals.`,
        );
        return;
      }
      updatePurchase({ amount });
    } else if (editing === "store") {
      if (!draft.trim()) {
        setError("Enter a store name.");
        return;
      }
      updatePurchase({ store: draft.trim() });
    }
    setEditing(null);
    setError("");
    Keyboard.dismiss();
  }
  async function send() {
    if (!message.trim() || sending) return;
    messageRequest.current?.abort();
    const pending = new AbortController();
    messageRequest.current = pending;
    setSending(true);
    setPendingKind("text");
    abandonRecording();
    try {
      const turn = await services.conversation.sendText(
        message.trim(),
        purchase,
        pending.signal,
      );
      if (pending.signal.aborted) return;
      if (turn.purchasePatch) updatePurchase(turn.purchasePatch);
      appendMessages([
        { role: "user", text: message.trim() },
        { role: "assistant", text: turn.reply },
      ]);
      setReply("");
      setMessage("");
      if (turn.voice) {
        playbackRequest.current?.abort();
        const playing = new AbortController();
        playbackRequest.current = playing;
        void services.playback.play(turn.voice, playing.signal).catch(() => {});
      }
    } catch (error) {
      if (!pending.signal.aborted) {
        setReply(
          error instanceof Error && error.message
            ? `Couldn't send that: ${error.message}`
            : "Message failed. Please try sending again.",
        );
      }
    } finally {
      // Clear the flag unless a newer send has already taken over. Keying
      // this on `aborted` left `sending` stuck true after any cancellation,
      // and every later send then returned early without making a request --
      // a composer that looked alive but did nothing.
      if (messageRequest.current === pending) {
        setSending(false);
        setPendingKind(null);
      }
    }
  }
  // Tap to start, tap again to stop and send -- single-shot, no partial
  // results while recording (matches the backend's non-goal of multi-turn
  // voice dialogue).
  async function toggleRecording() {
    if (listening) {
      setListening(false);
      await recorder.stop();
      const uri = recorder.uri;
      if (!uri) {
        setReply("Recording failed. Please try again or type instead.");
        return;
      }
      messageRequest.current?.abort();
      const pending = new AbortController();
      messageRequest.current = pending;
      setSending(true);
      setPendingKind("voice");
      try {
        const turn = await services.conversation.sendVoice(
          uri,
          "audio/m4a",
          purchase,
          pending.signal,
        );
        if (pending.signal.aborted) return;
        if (turn.purchasePatch) updatePurchase(turn.purchasePatch);
        const spoken = turn.transcript
          ? [{ role: "user" as const, text: turn.transcript }]
          : [];
        appendMessages([...spoken, { role: "assistant", text: turn.reply }]);
        setReply("");
        if (turn.voice) {
          playbackRequest.current?.abort();
          const playing = new AbortController();
          playbackRequest.current = playing;
          void services.playback.play(turn.voice, playing.signal).catch(() => {});
        }
      } catch (error) {
        if (!pending.signal.aborted) {
          setReply(
            error instanceof Error && error.message
              ? `Couldn't send that: ${error.message}`
              : "Message failed. Please try sending again.",
          );
        }
      } finally {
        if (messageRequest.current === pending) {
          setSending(false);
          setPendingKind(null);
        }
      }
      return;
    }

    if (startingRecording.current) return; // already starting; ignore the double-tap
    startingRecording.current = true;
    try {
      Keyboard.dismiss();
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) {
        setReply("Microphone access is needed to record. You can type instead.");
        return;
      }
      // iOS rejects allowsRecording without playsInSilentMode explicitly set
      // (see ExpoAudio/AudioUtils.swift) -- this call replaces the whole mode
      // rather than merging, so playsInSilentMode must be listed here too.
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      setReply("");
      setListening(true);
    } finally {
      startingRecording.current = false;
    }
  }
  async function compare() {
    if (loading) return;
    Keyboard.dismiss();
    abandonRecording();
    setLoading(true);
    request.current?.abort();
    const pending = new AbortController();
    request.current = pending;
    try {
      await requestComparison(pending.signal);
      if (!pending.signal.aborted) router.push("/recommendation");
    } catch (error) {
      if (!pending.signal.aborted) {
        setReply(
          error instanceof Error && error.message
            ? error.message
            : "Could not compare your cards. Please try again.",
        );
      }
    } finally {
      // Same rule as send(): only the current request may clear the flag.
      if (request.current === pending) setLoading(false);
    }
  }
  return (
    <SafeAreaView style={s.screen} edges={["top", "bottom", "left", "right"]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <View style={styles.header}>
          <Header
            title="Ask CreditPick"
            back
            onBack={() => router.dismissTo("/")}
          />
        </View>
        <ScrollView
          ref={scroll}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="interactive"
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
        >
          <View style={styles.voice}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={
                listening ? "Stop recording and send" : "Start recording"
              }
              onPress={() => void toggleRecording()}
              disabled={sending}
              style={({ pressed }) => [
                styles.outerCircle,
                pressed && s.pressed,
              ]}
            >
              <View
                style={[
                  styles.middleCircle,
                  listening && { backgroundColor: theme.colors.accentSurfaceStrong },
                ]}
              >
                <View style={styles.innerCircle}>
                  <Icon
                    name={listening ? "square" : "mic"}
                    size={listening ? 26 : 38}
                    color={listening ? theme.colors.accent : undefined}
                  />
                </View>
              </View>
            </Pressable>
            <View style={styles.wave} accessible={false}>
              {[8, 15, 25, 12, 31, 20, 13, 26, 16, 8, 18].map((height, i) => (
                <Animated.View
                  key={i}
                  style={{
                    width: 3,
                    height,
                    borderRadius: 3,
                    backgroundColor: theme.colors.accentBright,
                    transform: [
                      {
                        scaleY: wave.interpolate({
                          inputRange: [0, 1],
                          outputRange: i % 2 ? [0.5, 1] : [1, 0.4],
                        }),
                      },
                    ],
                  }}
                />
              ))}
            </View>
            <Copy accessibilityLiveRegion="polite" style={s.bold}>
              {listening
                ? "Listening… tap to stop"
                : ready
                  ? "Ready to compare"
                  : "Tell me what you're buying"}
            </Copy>
            <View
              style={[
                s.row,
                { justifyContent: "center", flexWrap: "wrap", gap: 6 },
              ]}
            >
              <Copy style={s.small}>
                {listening ? "Recording…" : "Tap the mic, or type below"}
              </Copy>
            </View>
          </View>
          <View style={{ gap: 12 }}>
            <ChatBubble>
              {ready
                ? `${purchase.store} · ${money(purchase.amount, purchase.amount % 1 ? 2 : 0)} · ${purchase.category}. Compare when you're ready.`
                : "What are you buying? Tell me the store and amount below, or tap a field to fill it in."}
            </ChatBubble>
          </View>
          {conversationMessages.map((entry, index) => (
            <ChatBubble key={index} user={entry.role === "user"}>
              {entry.text}
            </ChatBubble>
          ))}
          <View style={styles.chips}>
            {(
              [
                {
                  field: "store",
                  icon: "map-pin",
                  value: purchase.store || "Add store",
                  filled: !!purchase.store.trim(),
                },
                {
                  field: "category",
                  icon: "shopping-bag",
                  value: purchase.category,
                  filled: true,
                },
                {
                  field: "amount",
                  icon: "dollar-sign",
                  value:
                    purchase.amount > 0
                      ? money(purchase.amount, purchase.amount % 1 ? 2 : 0)
                      : "Add amount",
                  filled: purchase.amount > 0,
                },
              ] as const
            ).map((chip) => (
              <Pressable
                key={chip.field}
                accessibilityRole="button"
                accessibilityLabel={`Edit ${chip.field}: ${chip.value}`}
                onPress={() => edit(chip.field)}
                style={[styles.chip, !chip.filled && styles.chipEmpty]}
              >
                <Icon name={chip.icon} size={15} />
                <Copy
                  style={[
                    styles.chipText,
                    !chip.filled && { color: theme.colors.muted },
                  ]}
                >
                  {chip.value}
                </Copy>
                <Icon name="edit-2" size={11} color={theme.colors.muted} />
              </Pressable>
            ))}
          </View>
          {editing && (
            <View style={styles.editor}>
              <View style={s.row}>
                <Copy style={s.bold}>Edit {editing}</Copy>
                <IconButton
                  name="x"
                  label="Cancel editing"
                  onPress={() => {
                    setEditing(null);
                    setError("");
                    Keyboard.dismiss();
                  }}
                />
              </View>
              {editing === "category" ? (
                <View style={styles.chips}>
                  {categories.map((category) => (
                    <Pressable
                      accessibilityRole="button"
                      accessibilityState={{
                        selected: purchase.category === category,
                      }}
                      key={category}
                      style={[
                        styles.chip,
                        purchase.category === category && {
                          backgroundColor: theme.colors.accentSurfaceStrong,
                        },
                      ]}
                      onPress={() => {
                        updatePurchase({ category });
                        setEditing(null);
                      }}
                    >
                      <Copy>{category}</Copy>
                    </Pressable>
                  ))}
                </View>
              ) : (
                <>
                  <TextInput
                    keyboardAppearance="dark"
                    selectionColor={theme.colors.accent}
                    autoFocus
                    accessibilityLabel={`New ${editing}`}
                    value={draft}
                    onChangeText={setDraft}
                    keyboardType={
                      editing === "amount" ? "decimal-pad" : "default"
                    }
                    maxLength={editing === "amount" ? 12 : 60}
                    style={styles.input}
                    onSubmitEditing={save}
                    returnKeyType="done"
                  />
                  {!!error && (
                    <Copy
                      accessibilityRole="alert"
                      style={{ color: theme.colors.warning }}
                    >
                      {error}
                    </Copy>
                  )}
                  <Button title="Save changes" onPress={save} />
                </>
              )}
            </View>
          )}
          {sending && pendingKind && (
            <View style={[s.bubble, styles.statusBubble]}>
              <ActivityIndicator size="small" color={theme.colors.accent} />
              <Copy style={{ fontSize: 15, lineHeight: 22 }}>
                {(pendingKind === "voice" ? VOICE_STAGES : TEXT_STAGES)[
                  stageIndex
                ]}
              </Copy>
            </View>
          )}
          {!sending && !!reply && <ChatBubble>{reply}</ChatBubble>}
          {!editing && (
            <View style={{ gap: 4 }}>
              <Button
                title={loading ? "Comparing your cards…" : "Compare my cards"}
                icon="arrow-right"
                loading={loading}
                disabled={!ready}
                onPress={compare}
              />
              {!ready && (
                <Copy style={[s.small, { textAlign: "center" }]}>
                  Add a store and an amount to compare.
                </Copy>
              )}
              <TextAction title="Start over" onPress={reset} />
            </View>
          )}
        </ScrollView>
        <View style={{ paddingHorizontal: 24 }}>
          <View style={styles.composer}>
            <TextInput
              keyboardAppearance="dark"
              selectionColor={theme.colors.accent}
              ref={composer}
              accessibilityLabel="Type a message"
              placeholder="Type a message…"
              placeholderTextColor={theme.colors.muted}
              value={message}
              onChangeText={setMessage}
              onSubmitEditing={send}
              returnKeyType="send"
              maxLength={200}
              style={styles.composerInput}
              onFocus={abandonRecording}
            />
            {message.trim() ? (
              <IconButton
                name="arrow-up"
                label="Send message"
                onPress={send}
                filled
              />
            ) : (
              <IconButton
                name={listening ? "square" : "mic"}
                label={listening ? "Stop recording and send" : "Record a message"}
                onPress={() => void toggleRecording()}
                filled={listening}
              />
            )}
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  statusBubble: { flexDirection: "row", alignItems: "center", gap: 10 },
  header: {
    paddingHorizontal: 16,
    paddingTop: 8,
    width: "100%",
    maxWidth: 560,
    alignSelf: "center",
  },
  content: {
    padding: 24,
    paddingTop: 4,
    paddingBottom: 12,
    gap: 12,
    flexGrow: 1,
    width: "100%",
    maxWidth: 560,
    alignSelf: "center",
  },
  voice: { alignItems: "center", gap: 4, paddingBottom: 4 },
  outerCircle: {
    width: 112,
    height: 112,
    borderRadius: 56,
    backgroundColor: theme.colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  middleCircle: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: theme.colors.accentSurface,
    alignItems: "center",
    justifyContent: "center",
  },
  innerCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: theme.colors.accentSurfaceStrong,
    alignItems: "center",
    justifyContent: "center",
  },
  wave: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    height: 32,
    marginTop: -6,
  },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chipEmpty: { borderStyle: "dashed" },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    minHeight: 44,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 12,
    backgroundColor: theme.colors.accentSurface,
    maxWidth: "100%",
  },
  chipText: {
    fontSize: 12,
    lineHeight: 18,
    color: theme.colors.accent,
    fontWeight: "500",
    flexShrink: 1,
  },
  editor: {
    padding: 16,
    gap: 12,
    backgroundColor: theme.colors.surface,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 16,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 12,
    padding: 14,
    minHeight: 48,
    fontSize: 16,
    color: theme.colors.ink,
  },
  composer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    width: "100%",
    marginBottom: 8,
    padding: 6,
    paddingLeft: 16,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 28,
    backgroundColor: theme.colors.surface,
    maxWidth: 512,
    alignSelf: "center",
  },
  composerInput: {
    flex: 1,
    minHeight: 44,
    fontSize: 14,
    color: theme.colors.ink,
  },
});
