# CreditPick

The CreditPick app: React Native + Expo SDK 57 + TypeScript. Deep forest-green backgrounds, lighter green panels, vivid green accents, off-white headings, muted sage supporting text, and Feather line icons. Every figure it shows comes from the FastAPI backend; there is no local card data and no offline mode. No HTML, WebView, or microphone access.

The dark theme uses semantic color tokens, light status-bar content, dark keyboards, and a matching native navigation theme. Existing screen sizes, safe areas, font scaling, touch targets, and interactions are preserved. Warnings use amber with text/icons, keeping them distinct from green brand accents. Primary text/accent combinations were checked for at least 4.5:1 contrast. The styling follows Apple's [2026 iOS branding guidance](https://developer.apple.com/videos/play/wwdc2026/251/) and [materials guidance](https://developer.apple.com/design/human-interface-guidelines/materials): restrained accent color, familiar navigation, and separation between controls and content. This change uses opaque layered surfaces; it does not add a Liquid Glass renderer or replace the existing navigator.

## Run against the backend

Use Node 22.13 or newer. The app has no offline mode. Every figure comes from the FastAPI backend, so
start that first (see the root `README.md`), then:

```sh
npm install
EXPO_PUBLIC_API_URL=http://<your-lan-ip>:8000 npx expo start
```

`EXPO_PUBLIC_API_URL` must be your machine's LAN address, not `localhost`, for
a phone to reach it. It defaults to `http://localhost:8000`, which works only
in the browser.

## Flow

- Home lists your linked cards, with balances and utilization from `/dashboard`.
- The chat icon beside the microphone opens the composer. Ask a question and
  the backend answers it; the scoring engine computes the numbers and Gemini
  phrases them.
- The microphone is not connected yet — audio capture needs a streaming
  endpoint the backend does not have.
- Tap a purchase chip to edit the store, category, or amount ($0.01–$2,500).
- "Compare my cards" ranks every card and opens the recommendation screen.
- "View comparison" shows the full ranking. "Hear recommendation" plays the
  backend's audio when present, and falls back to device text-to-speech.

## Structure

`src/theme.ts` holds design tokens; `src/components/creditpick.tsx` contains reusable UI. `src/domain` contains shared models; `src/state` owns the purchase session and async resources. `src/services/contracts.ts` defines replaceable wallet, recommendation, conversation, voice-session, and playback interfaces. `src/services/index.ts` composes the HTTP implementation in `src/services/http-services.ts`, the one place that knows the backend's wire format. Screens never rank cards or compute rewards. `src/app` uses a native stack with Home, Conversation, and Recommendation. Conversation messages live in the provider and survive returning Home.

See [ARCHITECTURE.md](ARCHITECTURE.md) for backend ownership, cancellation semantics, DTO conventions, and the future backend/ElevenLabs audio path. The contracts are integration boundaries, not an implemented backend connection.

Home has a centered italic serif wordmark, a horizontal credit-card carousel, and a bottom-centered microphone with a conversation shortcut at the right edge. At normal text sizes, only the card carousel scrolls left and right; the voice controls stay anchored. Recommendation details and speech transcripts open in sheets. Scrolling remains available for very short displays, accessibility text, the keyboard, and longer lists/conversations so content stays reachable.

## Checks

```sh
npm run typecheck
npm test
npx expo export --platform ios --platform android
```

Tests cover wallet reconciliation, default estimates, edited amounts and categories, credit eligibility, validation, service responses, request cancellation, and voice-session cleanup. Both native bundles and TypeScript were checked. Visual and interactive device review is left to the user, as requested. Styling follows the written specification and layout feedback from the supplied simulator screenshots.

Suggested device review: Home → View all → card details → Show less → conversation icon → send a message → back to Home → reopen conversation and confirm transcript → edit all three chips → compare → comparison sheet → speech → ask another question. Repeat on a small screen with larger system text and the keyboard visible.

Expo APIs were checked against the [SDK 57 reference](https://docs.expo.dev/versions/v57.0.0/), [Router reference](https://docs.expo.dev/versions/v57.0.0/sdk/router/), and [Speech reference](https://docs.expo.dev/versions/v57.0.0/sdk/speech/).
