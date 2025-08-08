export default {
  content: ["./index.html", 
            "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ["'Roboto Mono'", 
               "ui-monospace",
               "SFMono-Regular",
               "monospace"],
      },
    },
  },
  plugins: [],
};
