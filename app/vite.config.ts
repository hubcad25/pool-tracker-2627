import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Servi par GitHub Pages sous /pool-tracker-2627/
export default defineConfig({
  base: '/pool-tracker-2627/',
  plugins: [react()],
  // Le proxy LNH (infra/aws/proxy_lnh.py) n'accepte que le port 5173 : échouer plutôt que glisser sur 5174
  server: { port: 5173, strictPort: true },
})
