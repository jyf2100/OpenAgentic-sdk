/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#1a1a2e',
        card: '#16213e',
        accent: '#0f4c75',
        text: '#eaeaea',
      },
    },
  },
  plugins: [],
}
