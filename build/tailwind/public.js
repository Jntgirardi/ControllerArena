module.exports = {
  darkMode: "class",
  content: [
    "../../templates/public_base.html",
    "../../templates/home_hltv.html",
    "../../templates/ranking.html",
    "../../templates/sumula_partida.html",
    "../../templates/detalhes_campeonato.html",
  ],
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/container-queries'),
  ],
  theme: {
    extend: {
      colors: {
        "primary": "#003ec7",
        "primary-container": "#0052ff",
        "on-primary": "#ffffff",
        "on-primary-container": "#dfe3ff",
        "secondary": "#5c5f60",
        "secondary-container": "#dee0e2",
        "on-secondary": "#ffffff",
        "on-secondary-container": "#606365",
        "background": "#f9f9ff",
        "on-background": "#141b2b",
        "surface": "#f9f9ff",
        "surface-white": "#FFFFFF",
        "surface-dim": "#d3daef",
        "surface-bright": "#f9f9ff",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f1f3ff",
        "surface-container": "#e9edff",
        "surface-container-high": "#e1e8fd",
        "surface-container-highest": "#dce2f7",
        "on-surface": "#141b2b",
        "on-surface-variant": "#434656",
        "outline": "#737688",
        "outline-variant": "#c3c5d9",
        "border-subtle": "#E5E7EB",
        "text-muted": "#6B7280",
        "live": "#ef4444",
        "success": "#10B981",
        "warning": "#F59E0B",
        "error": "#EF4444",
        "error-container": "#ffdad6",
        "brand-primary": "#003ec7",
        "brand-highlight": "#f59e0b",
        "brand-highlight-dark": "#b45309",
        "default-border": "#E5E7EB",
        "default-font": "#141b2b",
        "subtext": "#434656",
      },
      borderRadius: {
        "DEFAULT": "0.25rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "full": "9999px"
      },
      spacing: {
        "container-margin": "24px",
        "section-gap": "40px",
        "base": "4px",
        "card-padding": "20px",
        "gutter": "16px"
      },
      screens: {
        "mobile": {'max': '991px'},
      },
      fontFamily: {
        "body-lg": ["Inter", "sans-serif"],
        "headline-md": ["Chakra Petch", "sans-serif"],
        "display-score": ["Inter", "sans-serif"],
        "headline-lg": ["Chakra Petch", "sans-serif"],
        "body-md": ["Inter", "sans-serif"],
        "label-sm": ["Inter", "sans-serif"],
        "stats-mono": ["Inter", "sans-serif"]
      },
      fontSize: {
        "headline-lg": ["2rem", { lineHeight: "2.5rem" }],
        "headline-md": ["1.75rem", { lineHeight: "2.25rem" }],
        "body-md": ["0.875rem", { lineHeight: "1.25rem" }],
        "label-sm": ["0.75rem", { lineHeight: "1rem" }]
      }
    }
  }
}