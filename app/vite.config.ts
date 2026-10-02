import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Servi par GitHub Pages sous /pool-tracker-2627/
export default defineConfig({
  base: '/pool-tracker-2627/',
  plugins: [react()],
})
