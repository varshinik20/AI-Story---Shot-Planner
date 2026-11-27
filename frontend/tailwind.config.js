/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        sf: {
          bg: '#FFFFFF',
          sidebar: '#F9F9F9',
          text: '#212121',
          muted: '#6B7280',
          border: '#E5E7EB',
          hover: '#F1F1F1',
          userBubble: '#F4F4F4',
          accent: '#10A37F',
          accentHover: '#0D8A6B',
        },
      },
    },
  },
  plugins: [],
}
