module.exports = {
  content: [
    "../../templates/base.html",
    "../../templates/dashboard.html",
    "../../templates/relatorios.html",
    "../../templates/arbitros/*.html",
    "../../templates/campeonatos/*.html",
    "../../templates/jogadores/*.html",
    "../../templates/operador/*.html",
    "../../templates/partidas/*.html",
    "../../templates/times/*.html",
    "../../templates/usuarios/*.html",
  ],
  theme: {
    extend: {
      colors: {
        'brand-primary': '#5c59f2',
        'brand-primary-light': 'rgba(92, 89, 242, 0.08)',
        'brand-highlight': '#f59e0b',
        'brand-highlight-dark': '#b45309',
        'card-background': '#ffffff',
        'default-background': '#f5f5f5',
        'default-border': '#e5e5e5',
        'default-font': '#171717',
        'subtext': '#737373',
        'live': '#ef4444',
        'success': '#10b981',
        'success-light': '#d1fae5',
        'warning': '#f59e0b',
        'warning-light': '#fef3c7',
        'error': '#ef4444',

        'primary': '#5c59f2',
        'primary-container': '#5c59f2',
        'surface-white': '#FFFFFF',
        'background': '#f9f9ff',
        'border-border-subtle': '#E5E7EB',
        'border-subtle': '#E5E7EB',
        'surface-container': '#e9edff',
        'surface-container-low': '#f1f3ff',
        'text-muted': '#6B7280',
        'on-surface': '#141b2b',
        'on-surface-variant': '#434656',
      },
      spacing: {
        'base': '4px',
        'card-padding': '20px',
        'gutter': '16px',
        'section-gap': '40px',
      },
      screens: {
        'mobile': {'max': '991px'},
      }
    }
  }
}