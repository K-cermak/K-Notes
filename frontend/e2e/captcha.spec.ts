import { expect, test, type Page } from '@playwright/test'
import { admin, adminPage } from './helpers'

// A captcha applies to every sign-in on the instance, so this project runs after all the others
// (playwright.config.ts). ALTCHA is the one provider that works without the internet.

async function saveCaptcha(page: Page, provider: string): Promise<void> {
  const section = page.getByTestId('captcha-settings')
  await section.getByLabel('Captcha', { exact: true }).selectOption(provider)
  await section.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByTestId('snackbar')).toContainText('Changes saved')
}

test('with ALTCHA on, signing in needs the solved check', async ({ browser }) => {
  const { page, context } = await adminPage(browser)
  await saveCaptcha(page, 'altcha')
  try {
    const visitor = await browser.newContext()
    const login = await visitor.newPage()
    await login.goto('/login')

    const refused = await visitor.request.post('/api/v1/auth/login', {
      data: { email: admin.email, password: admin.password },
    })
    expect(refused.status()).toBe(400)

    const widget = login.frameLocator('[data-testid=captcha-frame]').locator('altcha-widget')
    await expect(widget).toContainText('Verified')
    await login.getByLabel('E-mail').fill(admin.email)
    await login.getByLabel('Password').fill(admin.password)
    await login.getByRole('button', { name: 'Sign in' }).click()
    await expect(login.getByTestId('sync-status')).toBeVisible()
    await visitor.close()
  } finally {
    // Through the API: it works even when the test failed halfway, and no second snackbar can
    // overlap the first one while it fades out.
    const off = await context.request.put('/api/v1/admin/captcha', {
      data: { provider: 'none', placement: 'both' },
    })
    expect(off.ok()).toBe(true)
    await context.close()
  }
})
