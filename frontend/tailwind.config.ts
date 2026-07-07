import type { Config } from 'tailwindcss'

/**
 * "Leaflet" — warm medical-hub design system (emerald + white, editorial type).
 * See docs/DESIGN.md. Every color/type/motion decision derives from these tokens;
 * components must not hardcode one-off values.
 */
const config: Config = {
  // Class-based dark mode: next-themes toggles `class="dark"` on <html>; default
  // is LIGHT (see app/providers.tsx). `dark:` variants key off that class.
  darkMode: 'class',
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Fresh, confident hero green — actions, accents, hero moments.
        emerald: {
          50: '#e8f8f0',
          100: '#cbeedd',
          200: '#9fe0c2',
          300: '#66cda2',
          400: '#2eb582',
          500: '#12a877',
          600: '#0b8e63',
          700: '#0b7250',
          800: '#0c5b42',
          900: '#0c4b37',
          950: '#053023',
        },
        // Warm green-neutral ink — text, borders, quiet neutrals.
        ink: {
          50: '#f4f7f5',
          100: '#e7ede9',
          200: '#d5ded9',
          300: '#b4c1b9',
          400: '#8b9a91',
          500: '#657069',
          600: '#4c554f',
          700: '#3a423d',
          800: '#262c29',
          900: '#161b18',
          950: '#0d100e',
        },
        // Clean white / mint-white surfaces.
        paper: {
          DEFAULT: '#f4faf6',
          raised: '#ffffff',
          sunken: '#eef6f1',
          dark: '#0d1512',
          'dark-raised': '#141d19',
          'dark-sunken': '#101815',
        },
        // Serious warm amber — refusal / insufficient evidence.
        caution: {
          50: '#fdf3e3',
          100: '#f8e2bd',
          200: '#efc985',
          300: '#e6b45c',
          400: '#db9a30',
          500: '#d08a1e',
          600: '#a86a10',
          700: '#84520e',
          800: '#6a420d',
          900: '#5a380c',
        },
        // Clear serious red — blocked / rejected evidence.
        danger: {
          50: '#fdecec',
          100: '#f8d3d3',
          200: '#f0acac',
          300: '#e88d8d',
          400: '#e05a5a',
          500: '#dc2626',
          600: '#c01f1f',
          700: '#9c1a1a',
          800: '#7f1919',
          900: '#6d1616',
        },
        // A tiny warm secondary spark (streaming, small highlights).
        honey: { DEFAULT: '#f4b740', soft: '#fbe6bd' },
      },
      fontFamily: {
        display: ['var(--font-display)', 'ui-serif', 'Georgia', 'serif'],
        sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      borderRadius: {
        lg: '10px',
        xl: '14px',
        '2xl': '18px',
        '3xl': '24px',
      },
      boxShadow: {
        // Soft, green-tinted, layered — cards feel liftable.
        card: '0 1px 2px rgba(16,40,32,0.05), 0 6px 16px -6px rgba(16,40,32,0.10)',
        soft: '0 10px 34px -10px rgba(16,40,32,0.16)',
        lift: '0 16px 44px -12px rgba(16,40,32,0.22)',
        glow: '0 0 0 3px rgba(18,168,119,0.18)',
      },
      letterSpacing: {
        label: '0.05em',
      },
      transitionDuration: {
        fast: '140ms',
        DEFAULT: '220ms',
        slow: '420ms',
      },
      keyframes: {
        caret: { '0%,100%': { opacity: '1' }, '50%': { opacity: '0' } },
        // Gentle emerald pulse on the live/active step.
        'pulse-dot': {
          '0%,100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.55', transform: 'scale(0.82)' },
        },
        'rise-in': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'flash-cite': {
          '0%': { backgroundColor: 'rgba(18,168,119,0.22)' },
          '100%': { backgroundColor: 'transparent' },
        },
        sheen: {
          '0%': { transform: 'translateX(-120%)' },
          '100%': { transform: 'translateX(120%)' },
        },
      },
      animation: {
        caret: 'caret 1.1s step-end infinite',
        'pulse-dot': 'pulse-dot 1.5s ease-in-out infinite',
        'rise-in': 'rise-in 0.4s cubic-bezier(0.2,0.7,0.2,1) both',
        'flash-cite': 'flash-cite 1.4s ease-out',
        sheen: 'sheen 1.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
export default config
