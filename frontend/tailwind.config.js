/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        blueprint: "#035a8c",
        panel: "#0369a1",
        well: "#075985",
        pale: "#e0f2fe",
        paler: "#bae6fd",
        alarm: "#fbbf24",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        heading: ["Sora", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
        hand: ["Caveat", "cursive"],
      },
    },
  },
  plugins: [],
};
