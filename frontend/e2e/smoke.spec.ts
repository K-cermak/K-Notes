import { expect, test } from '@playwright/test'

test('the first page shows the version from /config', async ({ page, request }) => {
  const config = (await (await request.get('/api/v1/config')).json()) as { version: string }
  await page.goto('/')
  await expect(page.getByTestId('version')).toContainText(config.version)
})

test('client routes survive a reload', async ({ page }) => {
  await page.goto('/showcase?theme=dark')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})

test('pages are served with a strict content security policy', async ({ page }) => {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  const response = await page.goto('/showcase')
  expect(response?.headers()['content-security-policy']).toContain("script-src 'self'")
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  expect(errors.filter((e) => e.includes('Content Security Policy'))).toEqual([])
})
