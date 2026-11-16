import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:18000',
    trace: 'retain-on-failure',
  },
  projects: [
    // Sets up the instance through the UI and creates the admin the other tests use.
    { name: 'accounts', testMatch: /accounts\.spec\.ts/, use: { ...devices['Desktop Chrome'] } },
    {
      name: 'chromium',
      testIgnore: /accounts\.spec\.ts/,
      dependencies: ['accounts'],
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
