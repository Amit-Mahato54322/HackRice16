# CreditPick frontend boundaries

The current implementation is a local demo. No HTTP endpoints, vendor SDK sessions, authentication, recording, or backend audio playback are connected yet.

## Ownership

| Layer | Responsibility |
| --- | --- |
| `src/app` | Native navigation, rendering, input, loading/error states |
| `src/state/creditpick-provider.tsx` | Wallet resource, purchase session, recommendation snapshot, invalidation |
| `src/domain/models.ts` | Shared types, currency formatting, input validation |
| `src/services/contracts.ts` | Provider-neutral wallet, recommendation, conversation, voice and playback contracts |
| `src/services/index.ts` | Select and inject implementations at one composition point |
| `src/services/mock-services.ts` + `src/data/demo.ts` | Demo data and business rules; replace with backend adapter |
| `src/services/device-playback.ts` | Demo text-to-speech fallback; replace with backend audio playback |

Screens do not import mock data, rank cards, calculate projected balances, or call speech SDKs. The recommendation response owns the selected card, alternatives, reward labels, reasons, utilization, threshold result, purchase snapshot, and voice output. Wallet responses own balances, utilization, and reward summaries.

## Backend integration

Implement `CreditPickServices` and inject it into `CreditPickProvider`, or change `src/services/index.ts`. No backend URL or endpoint schema is assumed yet. Keep HTTP response validation and conversion to these DTOs inside the adapter. `isDemo` and service `mode` distinguish demo data from live data; update the remaining demo-specific explanatory copy when enabling live mode.

Monetary DTO fields currently use USD major units. If the backend uses integer cents, convert once at the adapter boundary. Rewards, ranking, eligibility, balance freshness, and financial calculations should remain backend-owned. Do not add duplicate frontend ranking rules. The app treats the response as a snapshot of the submitted purchase.

Every asynchronous request accepts an `AbortSignal`. Leaving Conversation cancels pending message and comparison requests; leaving Recommendation stops playback. Purchase edits and resets invalidate recommendations, and a revision guard rejects results for an old purchase. Wallet failures have an explicit retry action. A failed comparison stays on the input screen; a playback failure retains the transcript. Backend adapters should preserve these cancellation/error semantics and map transport failures to safe user-facing states. Before production, define timeouts, error codes, schema validation, auth/token handling, telemetry and request IDs together with the backend contract.

## Voice / ElevenLabs

Intended flow: native microphone capture → `VoiceSession.sendAudio` → your backend → ElevenLabs → backend events → `VoiceEvent` → purchase state / UI. The backend owns vendor credentials and session creation. Audio chunks carry sequence and MIME information; negotiate sample rate, framing and transport with the backend before implementing capture. A session exposes `finish` and `close` for ending input and releasing resources.

The native capture adapter and backend transport are **not implemented**. The demo emits status events and explicitly rejects audio chunks. A live adapter must request microphone permission after a user action, handle denial/interruption, and clean up capture and transport on cancellation. Render backend turn events through the existing conversation handler. No ElevenLabs SDK should be imported into a screen.

Voice output is a transcript plus optional backend audio URL/MIME type. Implement native URL/stream playback behind `playback.play` when that backend output exists. The current device adapter speaks the transcript only. Preserve text fallback, stop controls and navigation cleanup. Streaming output can be added behind this boundary once the backend framing protocol is agreed.

## Layout

The native stack contains Home, Conversation, and Recommendation; there is no tab bar, Wallet screen, or Settings screen. Home shows featured cards and expands the full list inline. Card details use a sheet. The microphone stays centered near the bottom with a conversation shortcut on its right. Conversation has an explicit Home back action and keeps the composer outside its scrollable keyboard-aware content. Successful user messages and assistant replies are stored in the provider for the session; returning Home preserves them, and starting another question resets them.

Very short screens, larger accessibility text, the keyboard, and long conversation histories retain scrolling to keep content reachable. At normal sizes the Home card list scrolls internally while voice controls remain anchored. The wallet service contract remains the card-data boundary, despite removal of the Wallet UI. The demo threshold is fixed at 30%; the removed Settings UI no longer exposes a threshold setter. Visual verification remains with the user.

## Tests

`npm test` covers financial mock consistency, edited purchases, service response contracts, cancelled requests, and voice session disposal. `npm run typecheck` checks all adapters and screens. `npx expo export --platform ios --platform android` checks both native bundles. These checks do not replace device testing or production API contract tests.
