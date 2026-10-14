/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#25d366', // WhatsApp green
          600: '#128c7e', // WhatsApp teal
          700: '#075e54', // WhatsApp dark teal
          800: '#064e46',
          900: '#053f3a',
        },
      },
    },
  },
  plugins: [],
};
