import { Platform } from "react-native";

/** White surfaces, quiet neutrals, and soft blue-tinted elevation. */
export const theme = {
  colors: {
    background: "#F3F4F6",
    surface: "#FFFFFF",
    elevated: "#FFFFFF",
    ink: "#050506",
    muted: "#4E5263",
    subtle: "#AAA5B5",
    accent: "#050506",
    onAccent: "#FFFFFF",
    accentSurface: "#F3F4F6",
    accentSurfaceStrong: "#E7E9EF",
    accentBright: "#B5CCFC",
    positive: "#33529C",
    positiveBackground: "#E9EFFE",
    negative: "#A63A45",
    negativeBackground: "#FCECEF",
    warning: "#A63A45",
    warningBackground: "#FCECEF",
    border: "#ECEDF0",
    track: "#ECEDF0",
    marker: "#AAA5B5",
    cardEdge: "#ECEDF0",
    cardWash: "#FFFFFF",
    // Text on issuer artwork keeps its contrast independently of the page.
    cardInk: "#FFFFFF",
    cardMark: "#FFFFFF",
    cardMarkStem: "#B5CCFC",
    cardDecoration: "#FFFFFF14",
    cardBadge: "#050506B3",
    scrim: "#05050659",
  },
  fontFamily: Platform.select({
    ios: "System",
    android: "sans-serif",
    default:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
  }),
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  radius: { sm: 16, md: 20, lg: 24, pill: 999 },
  type: {
    small: 12,
    caption: 14,
    body: 16,
    subheading: 20,
    heading: 28,
    hero: 40,
  },
  shadow: {
    soft: "0px 4px 20px #4169B81A",
    lifted: "0px 8px 28px #4169B826",
    card: "0px 8px 24px #4169B82E",
    cardPressed: "0px 3px 10px #4169B81F",
  },
} as const;
