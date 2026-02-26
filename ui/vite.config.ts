import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Forward all /api and /health requests to the FastAPI server.
      // This means the browser talks only to localhost:5173 — no CORS needed.
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
});
