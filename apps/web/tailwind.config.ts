import type { Config } from "tailwindcss";

// Palette is taken verbatim from the brief. Extra warm-neutral tones are derived
// for borders/muted text so the terminal reads dense without introducing new hues.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0F1113",
        surface: "#181C20",
        "surface-2": "#1F242A",
        gold: "#C9A227",
        "gold-pale": "#CBB57B",
        bronze: "#A16B3B",
        positive: "#2B8A6E",
        negative: "#A54B4B",
        text: "#F4F1EA",
        muted: "#8C8579",
        hairline: "#2A2F35",
      },
      fontFamily: {
        sans: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
        serif: ["var(--font-plex-serif)", "Georgia", "serif"],
      },
      letterSpacing: {
        eyebrow: "0.22em",
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(201,162,39,0.06), 0 12px 40px -24px rgba(0,0,0,0.8)",
      },
      keyframes: {
        "pulse-soft": {
          "0%, 100%": { opacity: "0.35" },
          "50%": { opacity: "1" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-soft": "pulse-soft 1.4s ease-in-out infinite",
        "fade-up": "fade-up 0.35s ease both",
      },
    },
  },
  plugins: [],
};

export default config;
