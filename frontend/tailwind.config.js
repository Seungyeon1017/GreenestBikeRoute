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
      // GreenestBikeRoute headings, loaded in app/(greenest)/layout.tsx
      display: 'var(--font-display)',
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
        // GreenestBikeRoute palette: forest greens on warm paper tones
        leaf: {
          forest: '#1f3d2b',
          moss: '#3b6b4a',
          fern: '#5f8f63',
          sage: '#a9b99a',
          mint: '#e7efe3',
          cream: '#f7f4ec',
          sand: '#e6dfcf',
          ink: '#1b2420',
          muted: '#5e6a62',
        },
      },
      boxShadow: {
        soft: '0 1px 2px rgba(27, 36, 32, 0.04), 0 12px 32px -16px rgba(31, 61, 43, 0.22)',
      },
    },
  },
}
