# CardCue

A native React Native + Expo SDK 57 + TypeScript frontend demo. Warm off-white surfaces, forest-green cards and buttons, mint panels, and Feather line icons. No HTML, WebView, backend, authentication, bank integration, or microphone access.

## Run

Use Node 22.13+ (Node 24 recommended for the built-in TypeScript test runner).

```sh
npm install
npm start
```

Press `i` for iOS or `a` for Android, or scan the QR code in an Expo Go version supporting SDK 57. Direct commands: `npm run ios` / `npm run android`.

## Demo flow

- Home → microphone → simulated conversation → compare → recommendation.
- “Type instead” focuses the composer. Send an amount like `$125.50`; other messages receive scripted guidance.
- Tap any purchase chip to edit the store, category, or amount. Amounts must be $0.01–$2,500, with up to two decimal places.
- “View comparison” opens a dismissible bottom sheet. “Hear recommendation” uses device text-to-speech and also displays a transcript, including when speech is unavailable. iOS silent mode can mute speech.
- “Ask another question” restores the default purchase. Back navigation preserves edits.
- Wallet shows all ten sample cards and their details. Settings changes the session’s utilization threshold or resets the demo.

## Mock calculations

The ten local cards total a $10,000 limit, $1,800 balance, and $8,200 available credit: 18% utilization. Everyday Cash has a $3,146 illustrative limit and $646 balance. A $90 purchase leaves $2,410 available and produces 23.4% projected utilization when rounded to one decimal.

Only Everyday Cash and Travel Plus participate in purchase comparisons. Everyday Cash earns 3% on groceries and 1% otherwise; Travel Plus earns two points per dollar, with whole points rounded down. Ranking assumes 1¢ per point and prioritizes cards with sufficient available credit. Changing category may change the winning card. Changing the amount updates rewards, credit, and utilization. No balance is actually charged.

The 30% default threshold is a configurable reminder, not a credit-score guarantee. All financial information is demo data. “Latest synced balances” is reference UI copy; no sync takes place. State is memory-only and resets on app restart. Voice input is a short animation and scripted text; no recording or permission request occurs.

## Structure

`src/theme.ts` holds design tokens; `src/components/cardcue.tsx` contains reusable UI. `src/domain` contains shared models; `src/state` owns the purchase session and async resources. `src/services/contracts.ts` defines replaceable wallet, recommendation, conversation, voice-session, and playback interfaces. `src/services/index.ts` selects the local implementations. Screens do not import mock data or perform card ranking. `src/app` uses Expo Router’s native stack plus Home / Wallet / Settings tabs.

See [ARCHITECTURE.md](ARCHITECTURE.md) for backend ownership, cancellation semantics, DTO conventions, and the future backend/ElevenLabs audio path. The contracts are integration boundaries, not an implemented backend connection.

Home now uses a compact viewport layout instead of a scrolling page at normal text sizes, with a horizontal microphone prompt on shorter phones. Recommendation details and speech transcripts open in sheets. Scrolling remains available for very short displays, accessibility text, the keyboard, and longer lists/conversations so content stays reachable.

## Checks

```sh
npm run typecheck
npm test
npx expo export --platform ios --platform android
```

Tests cover wallet reconciliation, default estimates, edited amounts and categories, credit eligibility, validation, service responses, request cancellation, and voice-session cleanup. Both native bundles and TypeScript were checked. Visual and interactive device review is left to the user, as requested. Styling follows the written specification and layout feedback from the supplied simulator screenshots.

Suggested device review: Home → Type instead → edit all three chips → compare → comparison sheet → speech → back → ask another question; then open Wallet and Settings. Repeat on a small screen with larger system text and the keyboard visible.

Expo APIs were checked against the [SDK 57 reference](https://docs.expo.dev/versions/v57.0.0/), [Router reference](https://docs.expo.dev/versions/v57.0.0/sdk/router/), and [Speech reference](https://docs.expo.dev/versions/v57.0.0/sdk/speech/).
