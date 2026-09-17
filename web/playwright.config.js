import { defineConfig } from '@playwright/test'

const PY = 'C:\\Users\\lpf\\.conda\\envs\\novel-agent\\python.exe'

export default defineConfig({
  testDir: './e2e',
  timeout: 120000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
  },
  webServer: [
    {
      command: `"${PY}" -m novel_agent.cli.app serve --port 8000 --root ../`,
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: false,
      timeout: 60000,
      env: { ...process.env, NOVEL_ENGINE_MOCK: '1' },
    },
    {
      command: 'npm run dev -- --port 5173 --strictPort',
      url: 'http://localhost:5173',
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
})
