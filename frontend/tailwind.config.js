/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  theme: {
    screens: {
      xs: '540px',
      md: '768px',
      lg: '1024px',
      xl: '1440px',
      '2xl': '1920px',
    },
    fontFamily: {
      inter: 'var(--font-inter)',
      lexend: 'var(--font-lexend)',
      lora: 'var(--font-lora)',
    },
    extend: {
      container: {
        screens: {
          lg: '1024px',
          xl: '1440px',
          // 'xl' : '1024px',
          '2xl': '1920px',
        },
      },
      borderRadius: {
        md: 'var(--border-radius-md)',
        lg: 'var(--border-radius-lg)',
      },
      colors: {
        primary: {
          DEFAULT: 'rgb(var(--color-primary))',
          light: 'rgb(var(--color-primary-light))',
        },
        secondary: {
          DEFAULT: 'rgb(var(--color-secondary))',
          light: 'rgb(var(--color-secondary-light))',
        },
        climate: {
          DEFAULT: 'rgb(var(--color-climate))',
          light: 'rgb(var(--color-climate-light))',
        },
        mobility: {
          DEFAULT: 'rgb(var(--color-mobility))',
          light: 'rgb(var(--color-mobility-light))',
        },
        energy: {
          DEFAULT: 'rgb(var(--color-energy))',
          light: 'rgb(var(--color-energy-light))',
        },
        buildings: {
          DEFAULT: 'rgb(var(--color-buildings))',
          light: 'rgb(var(--color-buildings-light))',
        },
      },
    },
  },
}
