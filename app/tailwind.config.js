/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"] },
      colors: {
        ink: { DEFAULT: "#0f172a", soft: "#475569", faint: "#94a3b8", line: "#e2e8f0", wash: "#f8fafc" },
        symptom: { DEFAULT: "#0d9488", soft: "#ccfbf1" },
        machinery: { DEFAULT: "#4f46e5", soft: "#e0e7ff" },
        hypothesis: { DEFAULT: "#7c3aed", soft: "#ede9fe" },
        proof: { DEFAULT: "#b45309", soft: "#fef3c7" },
        caution: { DEFAULT: "#c2410c", soft: "#ffedd5" },
      },
    },
  },
  plugins: [],
};
