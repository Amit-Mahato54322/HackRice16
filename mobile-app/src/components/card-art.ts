import type { ImageSourcePropType } from "react-native";

/**
 * How a card looks.
 *
 * VectorMint publishes no artwork -- its card objects carry issuer, network
 * and URLs, and the /assets endpoint is broken -- so there is no API to pull
 * images from. Two sources instead:
 *
 * 1. A real image, if one has been dropped into assets/cards/ and registered
 *    in CARD_IMAGES below. Issuer card art is their copyright, so nothing is
 *    bundled by default.
 * 2. Otherwise the issuer's own palette, which makes each card recognisable
 *    as that bank's card without claiming to be a photograph of it.
 */

/** Issuer id from VectorMint -> that bank's brand colours. */
const ISSUER_THEMES: Record<string, { background: string; accent: string }> = {
  chase: { background: "#124A8B", accent: "#7FB2E5" },
  "capital-one": { background: "#12365E", accent: "#D03027" },
  "bank-of-america": { background: "#9B1B2E", accent: "#E4B7BD" },
  "american-express": { background: "#1D7BBF", accent: "#BFE1F5" },
  citi: { background: "#0B3B75", accent: "#D9282F" },
  discover: { background: "#1F4E79", accent: "#F58220" },
  "wells-fargo": { background: "#8C1D2C", accent: "#F2C75C" },
  "us-bank": { background: "#0B3D5C", accent: "#C8102E" },
  barclays: { background: "#0B4C8C", accent: "#6FA8DC" },
  synchrony: { background: "#2C3E73", accent: "#9BA6D4" },
};

/** Fallbacks for anything not listed above, kept in the app's own palette. */
const NEUTRAL_THEMES = [
  { background: "#145138", accent: "#63DDA0" },
  { background: "#1C5942", accent: "#8CD9B4" },
  { background: "#225D44", accent: "#A2CBB3" },
  { background: "#164632", accent: "#7FC8A4" },
];

/**
 * Real card artwork, keyed by VectorMint card id.
 *
 * To add one: drop the file in assets/cards/ and register it here, e.g.
 *
 *   "chase-sapphire-preferred": require("../../assets/cards/chase-sapphire-preferred.png"),
 *
 * require() needs a literal path, so this map cannot be built dynamically.
 * Anything absent simply falls back to the issuer palette.
 */
export const CARD_IMAGES: Record<string, ImageSourcePropType> = {
  "chase-sapphire-preferred": require("../../assets/cards/chase-sapphire-preferred.png"),
  "capital-one-venture": require("../../assets/cards/capital-one-venture.png"),
  "bofa-customized-cash": require("../../assets/cards/bofa-customized-cash.png"),
  "chase-freedom-unlimited": require("../../assets/cards/chase-freedom-unlimited.png"),
  "amex-blue-cash-preferred": require("../../assets/cards/amex-blue-cash-preferred.png"),
};

export type CardArt = {
  image?: ImageSourcePropType;
  background: string;
  accent: string;
};

export function cardArt(
  productId: string | undefined,
  issuer: string | undefined,
  index: number,
): CardArt {
  const theme =
    (issuer && ISSUER_THEMES[issuer.toLowerCase().replace(/\s+/g, "-")]) ||
    NEUTRAL_THEMES[index % NEUTRAL_THEMES.length];

  return {
    image: productId ? CARD_IMAGES[productId] : undefined,
    ...theme,
  };
}
