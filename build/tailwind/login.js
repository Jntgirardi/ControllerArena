module.exports = {
  darkMode: "class",
  content: [
    "../../templates/login.html",
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
        "background": "#f9f9ff",
        "on-background": "#141b2b",
        "surface": "#f9f9ff",
        "surface-white": "#FFFFFF",
        "surface-dim": "#d3daef",
        "on-surface": "#141b2b",
        "on-surface-variant": "#434656",
        "outline": "#737688",
        "outline-variant": "#c3c5d9",
        "border-subtle": "#E5E7EB",
        "text-muted": "#6B7280",
        "error": "#EF4444",
        "success": "#10B981"
      },
      borderRadius: {
        "DEFAULT": "0.25rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "full": "9999px"
      }
    }
  }
}