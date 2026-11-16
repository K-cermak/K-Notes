import { expect, type Browser, type BrowserContext, type Page } from '@playwright/test'

export const admin = { name: 'Ada Admin', email: 'ada@example.com', password: 'admin-password' }

let counter = 0

/** A fresh user per test, invited by the admin through the API, so parallel tests do not share notes. */
export async function newUser(browser: Browser): Promise<{ email: string; password: string }> {
  const context = await browser.newContext()
  await context.request.post('/api/v1/auth/login', {
    data: { email: admin.email, password: admin.password },
  })
  const invite = (await (
    await context.request.post('/api/v1/admin/invites', { data: {} })
  ).json()) as {
    url: string
  }
  counter += 1
  const user = { email: `user-${Date.now()}-${counter}@example.com`, password: 'user-password' }
  const accepted = await context.request.post('/api/v1/auth/invite/accept', {
    data: {
      token: invite.url.split('/').pop(),
      email: user.email,
      display_name: 'Tester',
      password: user.password,
    },
  })
  expect(accepted.ok()).toBe(true)
  await context.close()
  return user
}

/** A browser signed in as the user, showing the notes page. */
export async function signedIn(
  browser: Browser,
  user: { email: string; password: string },
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext()
  const login = await context.request.post('/api/v1/auth/login', {
    data: { email: user.email, password: user.password },
  })
  expect(login.ok()).toBe(true)
  const page = await context.newPage()
  await page.goto('/')
  await expect(page.getByTestId('sync-status')).toHaveAttribute('data-state', 'synced')
  return { context, page }
}
