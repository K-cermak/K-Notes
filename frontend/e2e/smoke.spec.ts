import { expect, test } from '@playwright/test'

test('placeholder page shows the version from /config', async ({ page, request }) => {
  const config = (await (await request.get('/api/v1/config')).json()) as { version: string }
  await page.goto('/')
  await expect(page.getByTestId('version')).toContainText(config.version)
})

test('client routes survive a reload', async ({ page }) => {
  await page.goto('/showcase?theme=dark')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})
