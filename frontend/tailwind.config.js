/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // calm travel palette with one accent (teal); ink and sand neutrals meet WCAG AA on each other
        ink: { 900: "#1c2430", 700: "#3b4656", 500: "#5b6676" },
        sand: { 50: "#fbfaf7", 100: "#f4f1ea", 200: "#e7e1d4", 300: "#d6cdbb" },
        accent: { 50: "#e8f5f3", 100: "#cdebe6", 600: "#0f766e", 700: "#0b5e58", 800: "#094b47" },
        warn: { 50: "#fdf3e7", 700: "#9a4a07" },
        bad: { 50: "#fdecec", 700: "#a12121" },
      },
      fontFamily: {
        sans: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};
