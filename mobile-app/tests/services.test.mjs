import assert from "node:assert/strict";
import test from "node:test";
import { createMockServices, delay } from "../src/services/mock-services.ts";

const playback = { async play() {}, async stop() {} };
const services = createMockServices(playback);
const signal = () => new AbortController().signal;

test("service flow returns complete wallet, purchase and recommendation DTOs", async () => {
  const wallet = await services.wallet.get(signal());
  assert.equal(wallet.cards.length, 10);
  assert.equal(
    wallet.available,
    wallet.cards.reduce((total, card) => total + card.available, 0),
  );
  assert.equal(wallet.cards[0].rewardSummary, "3% on groceries");
  const turn = await services.conversation.sendText(
    "$120",
    services.initialPurchase,
    signal(),
  );
  const purchase = { ...services.initialPurchase, ...turn.purchasePatch };
  const result = await services.recommendations.compare(purchase, 30, signal());
  assert.equal(result.best.card.id, "everyday");
  assert.equal(result.best.rewardLabel, "$3.60 cash back");
  assert.equal(result.best.available, 2380);
  assert.equal(result.alternatives[0].rewards, 240);
  assert.equal(result.reasons.length, 3);
  assert.ok(result.voice.transcript.includes("$3.60"));
  assert.deepEqual(result.purchase, purchase);
});

test("cancelled service requests reject instead of delivering stale results", async () => {
  const request = new AbortController();
  const pending = services.recommendations.compare(
    services.initialPurchase,
    30,
    request.signal,
  );
  request.abort();
  await assert.rejects(pending, /cancelled/);
  await assert.rejects(services.wallet.get(request.signal), /cancelled/);
});

test("voice session disposes timers on cancellation and never captures audio", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const events = [];
  const request = new AbortController();
  const session = await services.voice.start(
    (event) => events.push(event),
    request.signal,
  );
  assert.deepEqual(events, [{ type: "status", status: "listening" }]);
  await assert.rejects(
    session.sendAudio({
      bytes: new Uint8Array(),
      mimeType: "audio/pcm",
      sequence: 0,
    }),
    /disabled/,
  );
  request.abort();
  t.mock.timers.tick(5000);
  assert.equal(events.length, 1);
  session.close();
});

test("voice finish ends the session and typed unsupported input stays explicit", async () => {
  const events = [];
  const session = await services.voice.start(
    (event) => events.push(event),
    signal(),
  );
  await session.finish();
  assert.equal(events.at(-1).status, "idle");
  const turn = await services.conversation.sendText(
    "Hello",
    services.initialPurchase,
    signal(),
  );
  assert.equal(turn.purchasePatch, undefined);
  assert.match(turn.reply, /scripted demo/);
});

test("already cancelled delays settle immediately", async () => {
  const request = new AbortController();
  request.abort();
  await assert.rejects(delay(10000, request.signal), /cancelled/);
});
