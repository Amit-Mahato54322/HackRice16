import { router, useLocalSearchParams, useFocusEffect } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
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
  Button,
  ChatBubble,
  Copy,
  Header,
  Icon,
  IconButton,
  s,
} from "@/components/creditpick";
import { categories, money, Purchase, validateAmount } from "@/domain/models";
import { useCreditPick } from "@/state/creditpick-provider";
import { theme } from "@/theme";

export default function ConversationScreen() {
  const { typing } = useLocalSearchParams<{ typing?: string }>();
  const {
    purchase,
    conversationMessages,
    appendMessages,
    flowId,
    updatePurchase,
    services,
    compare: requestComparison,
  } = useCreditPick();
  const [listening, setListening] = useState(typing !== "1");
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
  const [sending, setSending] = useState(false);
  const wave = useRef(new Animated.Value(0)).current;

  useFocusEffect(
    useCallback(() => {
      setLoading(false);
      setSending(false);
      return () => {
        request.current?.abort();
        messageRequest.current?.abort();
        setListening(false);
      };
    }, []),
  );
  useEffect(() => {
    request.current?.abort();
    messageRequest.current?.abort();
    setMessage("");
    setReply("");
    setEditing(null);
    setError("");
    setLoading(false);
    setSending(false);
    setListening(typing !== "1");
  }, [flowId, typing]);
  useEffect(() => {
    if (typing !== "1") return;
    const focus = setTimeout(() => composer.current?.focus(), 350);
    return () => clearTimeout(focus);
  }, [typing]);
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
    const voiceRequest = new AbortController();
    let closeSession: (() => void) | undefined;
    void services.voice
      .start((event) => {
        if (voiceRequest.signal.aborted) return;
        if (event.type === "status" && event.status === "idle")
          setListening(false);
        if (event.type === "turn") {
          if (event.turn.purchasePatch)
            updatePurchase(event.turn.purchasePatch);
          appendMessages([{ role: "assistant", text: event.turn.reply }]);
        }
        if (event.type === "error") {
          setReply(event.message);
          setListening(false);
        }
      }, voiceRequest.signal)
      .then((session) => {
        if (voiceRequest.signal.aborted) session.close();
        else closeSession = session.close;
      })
      .catch(() => {
        if (!voiceRequest.signal.aborted) {
          setReply("Voice is unavailable. You can type instead.");
          setListening(false);
        }
      });
    return () => {
      active = false;
      voiceRequest.abort();
      closeSession?.();
      animation.stop();
      wave.setValue(0);
    };
  }, [listening, wave, services]);

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
    setListening(false);
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
    } catch {
      if (!pending.signal.aborted)
        setReply("Message failed. Please try sending again.");
    } finally {
      if (!pending.signal.aborted) setSending(false);
    }
  }
  async function compare() {
    if (loading) return;
    Keyboard.dismiss();
    setListening(false);
    setLoading(true);
    request.current?.abort();
    const pending = new AbortController();
    request.current = pending;
    try {
      await requestComparison(pending.signal);
      if (!pending.signal.aborted) router.push("/recommendation");
    } catch {
      if (!pending.signal.aborted)
        setReply("Could not compare your cards. Please try again.");
    } finally {
      if (!pending.signal.aborted) setLoading(false);
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
              accessibilityLabel="Voice input is not connected yet. Type your purchase below."
              onPress={() => {
                setListening(false);
                requestAnimationFrame(() => setListening(true));
              }}
              style={styles.outerCircle}
            >
              <View style={styles.middleCircle}>
                <View style={styles.innerCircle}>
                  <Icon name="mic" size={38} />
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
              {listening ? "Listening…" : "Ready to compare"}
            </Copy>
            <View
              style={[
                s.row,
                { justifyContent: "center", flexWrap: "wrap", gap: 6 },
              ]}
            >
              <Copy style={s.small}>
                Voice input isn’t connected yet · Type below
              </Copy>
            </View>
          </View>
          <View style={{ gap: 12 }}>
            <ChatBubble user>
              I’m buying {purchase.category.toLowerCase()} at {purchase.store}.
            </ChatBubble>
            <ChatBubble>About how much will you spend?</ChatBubble>
            <ChatBubble user>
              {money(purchase.amount, purchase.amount % 1 ? 2 : 0)}.
            </ChatBubble>
            <ChatBubble>Got it! Here’s what I heard:</ChatBubble>
          </View>
          {conversationMessages.map((entry, index) => (
            <ChatBubble key={index} user={entry.role === "user"}>
              {entry.text}
            </ChatBubble>
          ))}
          <View style={styles.chips}>
            {(
              [
                { field: "store", icon: "map-pin", value: purchase.store },
                {
                  field: "category",
                  icon: "shopping-bag",
                  value: purchase.category,
                },
                {
                  field: "amount",
                  icon: "dollar-sign",
                  value: money(purchase.amount, purchase.amount % 1 ? 2 : 0),
                },
              ] as const
            ).map((chip) => (
              <Pressable
                key={chip.field}
                accessibilityRole="button"
                accessibilityLabel={`Edit ${chip.field}: ${chip.value}`}
                onPress={() => edit(chip.field)}
                style={styles.chip}
              >
                <Icon name={chip.icon} size={15} />
                <Copy style={styles.chipText}>{chip.value}</Copy>
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
          {!!reply && <ChatBubble>{reply}</ChatBubble>}
          {!editing && (
            <Button
              title={loading ? "Comparing your cards…" : "Compare my cards"}
              icon="arrow-right"
              loading={loading}
              onPress={compare}
            />
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
              onFocus={() => setListening(false)}
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
                name="mic"
                label="Voice input not connected"
                onPress={() => {
                  Keyboard.dismiss();
                  setListening(false);
                  requestAnimationFrame(() => setListening(true));
                }}
                filled
              />
            )}
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
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
