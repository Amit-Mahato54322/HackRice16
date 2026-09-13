# Minimal icons

Raw SVG assets for the light theme. Each uses a `24 24` viewBox and explicit
colors, with rounded 1.5px strokes on outline icons.

| Assets                                  | Appearance                                              |
| --------------------------------------- | ------------------------------------------------------- |
| `buy.svg`, `sell.svg`, `exchange.svg`   | Near-black direction arrows for action cards            |
| `back.svg`, `bell.svg`                  | Near-black header outlines                              |
| `bell-alert.svg`                        | Bell with a pastel blue notification dot                |
| `home-active.svg`                       | Solid near-black home inside a soft gray rounded square |
| `menu.svg`, `analytics.svg`, `user.svg` | Muted gray navigation outlines                          |

Keep a visible label or accessible name on the host control. Use the alert
variant only when actual unread alerts exist. The SVG art is 24px; interactive
controls should retain the app's larger touch targets.

These are reusable visual assets for applicable or future controls. The current
app has no Buy, Sell, Exchange, or bottom-tab destinations, so the assets do not
add controls, alerts, or navigation behavior. No SVG renderer or dependency is
added. Existing native icons continue to use the installed icon library.
