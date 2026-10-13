import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
  test: { environment: 'jsdom', setupFiles: ['./tests/setup.ts'], css: true, env: { VITE_DEFAULT_LOCALE: 'zh' } },
});
