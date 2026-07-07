import type { Config } from 'tailwindcss'

/**
 * "Monograph" design system — an FDA drug reference rendered as a live clinical
 * instrument. See docs/DESIGN.md. Every color/type/motion decision derives from
 * these tokens; components must not hardcode one-off values.
 */
const config: Config = {
  darkMode: 'media',
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Cool slate-navy neutral — reference paper + printed ink.
        ink: {
          50: '#edf1f6',
          100: '#e1e7ef',
          200: '#cdd6e1',
          300: '#aab7c6',
          400: '#7e8c9c',
          500: '#5b6b7d',
          600: '#465565',
          700: '#374453',
          800: '#222e3c',
          900: '#14212e',
          950: '#0b131e',
        },
        // The page/card surfaces (cool clinical off-white, NOT cream).
        paper: {
          DEFAULT: '#e8edf3',
          raised: '#ffffff',
          sunken: '#f4f7fa',
          dark: '#0b131e',
          'dark-raised': '#121d2b',
          'dark-sunken': '#0f1927',
        },
        // The one confident accent — official-document ink (interactive + brand).
        cobalt: {
          50: '#edeffb',
          100: '#dce0f7',
          200: '#bac2ef',
          300: '#8e9be6',
          400: '#5d6fd8',
          500: '#3a50cc',
          600: '#2743c0',
          700: '#1e349b',
          800: '#1a2c7e',
          900: '#182769',
          950: '#0f1740',
        },
        // Instrument-live signal — analytical readout cyan (panel-only, live-only).
        cyan: {
          50: '#e2f8fb',
          100: '#c3f0f6',
          200: '#8fe3ee',
          300: '#4fd1e1',
          400: '#1fbfd3',
          500: '#0fb5c9',
          600: '#0c93a4',
          700: '#0c7684',
          800: '#0f5f6b',
          900: '#114e58',
          950: '#052f37',
        },
        // Serious amber — refusal / insufficient evidence (caution, not alarm).
        caution: {
          50: '#fbf2df',
          100: '#f6e6c0',
          200: '#eccd86',
          300: '#dfb157',
          400: '#ce9430',
          500: '#b77c1a',
          600: '#9a5b00',
          700: '#7e4a06',
          800: '#663d0c',
          900: '#56340f',
        },
        // Clinical red — blocked / rejected evidence (serious, non-neon).
        danger: {
          50: '#fbe9e8',
          100: '#f6d3d1',
          200: '#ecaca9',
          300: '#e08480',
          400: '#d4574f',
          500: '#c6302b',
          600: '#b3241f',
          700: '#951c18',
          800: '#7a1b18',
          900: '#661a18',
        },
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['var(--font-serif)', 'ui-serif', 'Georgia', 'serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      borderRadius: {
        sm: '4px',
        DEFAULT: '6px',
        md: '6px',
        lg: '10px',
        xl: '12px',
      },
      boxShadow: {
        // Faint, cool-tinted — the instrument reads through rules, not shadows.
        card: '0 1px 2px rgba(20, 33, 46, 0.05), 0 1px 1px rgba(20, 33, 46, 0.04)',
        raised: '0 4px 16px -6px rgba(20, 33, 46, 0.16)',
        glow: '0 0 0 1px rgba(15, 181, 201, 0.5), 0 0 12px -2px rgba(15, 181, 201, 0.45)',
      },
      letterSpacing: {
        label: '0.06em', // uppercase mono instrument labels
      },
      transitionDuration: {
        fast: '120ms',
        DEFAULT: '200ms',
        slow: '380ms',
      },
      keyframes: {
        caret: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        // The live instrument "reading" pulse — a cyan LED.
        'led-pulse': {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 0 0 rgba(15,181,201,0.55)' },
          '50%': { opacity: '0.55', boxShadow: '0 0 0 4px rgba(15,181,201,0)' },
        },
        // A single instrument scan sweep behind the active stage row.
        scan: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        'row-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'flash-cite': {
          '0%': { backgroundColor: 'rgba(15, 181, 201, 0.28)' },
          '100%': { backgroundColor: 'transparent' },
        },
      },
      animation: {
        caret: 'caret 1.1s step-end infinite',
        'led-pulse': 'led-pulse 1.4s ease-in-out infinite',
        scan: 'scan 1.6s ease-in-out infinite',
        'row-in': 'row-in 0.28s ease-out both',
        'flash-cite': 'flash-cite 1.4s ease-out',
      },
    },
  },
  plugins: [],
}
export default config
