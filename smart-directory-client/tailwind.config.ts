import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        violet: '#5C14EC',
        navy: '#14044C',
        pearl: '#FCFBFC',
        forest: '#417B5A',
        dark: '#1F271B',
      },
      fontFamily: {
        display: ['"Space Mono"', 'monospace'],
        body: ['"DM Sans"', 'sans-serif'],
      },
    },
  },
}
export default config