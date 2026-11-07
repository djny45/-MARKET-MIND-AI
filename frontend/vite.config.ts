import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react],
  // GitHub Pages serves project sites from /<repository-name>/.
  // Local development and self-hosted deployments retain the root path.
  base: process.env.VITE_BASE_PATH || '/',
})
