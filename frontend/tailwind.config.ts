import type { Config } from 'tailwindcss'

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
        // Warm, calming soft-green health palette.
        sage: {
          50: '#f2f8f4',
          100: '#e2f0e7',
          200: '#c6e1d1',
          300: '#9dcbb1',
          400: '#6dad8b',
          500: '#4b9270',
          600: '#39755b',
          700: '#2e5d49',
          800: '#274b3c',
          900: '#213e33',
          950: '#0f231c',
        },
      },
      fontFamily: {
        sans: [
          'ui-rounded',
          '"SF Pro Rounded"',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(0.8)', opacity: '0.7' },
          '70%, 100%': { transform: 'scale(1.9)', opacity: '0' },
        },
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'highlight-flash': {
          '0%': { backgroundColor: 'rgba(109, 173, 139, 0.35)' },
          '100%': { backgroundColor: 'transparent' },
        },
      },
      animation: {
        blink: 'blink 1s step-end infinite',
        'pulse-ring': 'pulse-ring 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in-up': 'fade-in-up 0.35s ease-out both',
        'highlight-flash': 'highlight-flash 1.4s ease-out',
      },
    },
  },
  plugins: [],
}
export default config
