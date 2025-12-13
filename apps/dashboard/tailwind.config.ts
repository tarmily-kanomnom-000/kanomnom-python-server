import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        "butter-0": "#fff9e7",
        "butter-1": "#ffe294",
        "butter-2": "#f7ca4e",
        "chocolate-1": "#421b11",
        "instagram-peach": "#fde7c3",
        "instagram-pink": "#f3c2d1",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
      animation: {
        fadeIn: "fadeIn 0.5s ease-in-out forwards 1.0s",
      },
    },
  },
  plugins: [],
} satisfies Config;
