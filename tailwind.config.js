/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './website/templates/**/*.html',
    './marketplace/templates/**/*.html',
    './registration/templates/**/*.html',
    './credits/templates/**/*.html',
    './tourism/templates/**/*.html',
    './royal_cards/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#395144', // rgb(57 81 68)
          '50': '#f2f6f4', 
          '100': '#e6ede9',
          '200': '#c0d2c8',
          '300': '#9ab6a7',
          '400': '#749a85',
          '500': '#4e7f63',
          '600': '#395144', // Primary color
          '700': '#2a3c33',
          '800': '#1b2822',
          '900': '#0d1411',
          '950': '#040705',
        },
        secondary: {
          DEFAULT: '#f59e0b',
          '50': '#fffbeb',
          '100': '#fef3c7',
          '200': '#fde68a',
          '300': '#fcd34d',
          '400': '#fbbf24',
          '500': '#f59e0b',
          '600': '#d97706',
          '700': '#b45309',
          '800': '#92400e',
          '900': '#78350f',
          '950': '#451a03',
        },
        kikapu: {
          'dark': '#395144',
          'medium': '#4E6C50',
          'light': '#AA8B56',
          'beige': '#F0EBCE',
        }
      },
      boxShadow: {
        'soft': '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)',
        'hover': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.6s ease-out forwards',
        'fade-in': 'fadeIn 0.6s ease-out forwards',
      },
      keyframes: {
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem',
      },
    },
  },
  plugins: [],
}