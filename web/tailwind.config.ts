import type { Config } from 'tailwindcss'
export default {
  darkMode: 'class',
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: { extend: { boxShadow: { soft: '0 12px 40px rgba(15,23,42,.08)' } } },
  plugins: []
} satisfies Config
