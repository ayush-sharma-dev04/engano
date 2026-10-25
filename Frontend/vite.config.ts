import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The repo's one .env (next to the Makefile) also holds the web app's settings. Vite only ever exposes
// variables that start with VITE_, so the backend's secrets in the same file never reach the browser.
export default defineConfig({
  envDir: '..',
  plugins: [react(), tailwindcss()],
})