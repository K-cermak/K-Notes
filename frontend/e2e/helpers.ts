import { expect, type Browser, type BrowserContext, type Page } from '@playwright/test'

export const admin = { name: 'Ada Admin', email: 'ada@example.com', password: 'admin-password' }

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
  // Workers run in parallel, so a timestamp alone can repeat.
  const user = { email: `user-${crypto.randomUUID()}@example.com`, password: 'user-password' }
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

/** Writes a note through the "Take a note…" composer. */
export async function addNote(page: Page, title: string, body = ''): Promise<void> {
  await page.getByTestId('composer').click()
  const form = page.getByTestId('note-form')
  await form.getByTestId('editor-title').fill(title)
  if (body) {
    await form.getByTestId('editor-body').click()
    await page.keyboard.type(body)
  }
  await form.getByTestId('close-note').click()
  // The card appears with the title alone after the first autosave; wait for the final save too.
  await expect(card(page, title)).toBeVisible()
  if (body) await expect(card(page, title).getByTestId('card-body')).toContainText(body)
  await expect(page.getByTestId('note-form')).toHaveCount(0)
}

export function card(page: Page, title: string) {
  return page
    .getByTestId('note-card')
    .filter({ has: page.getByTestId('card-title').getByText(title, { exact: true }) })
}

export async function openNote(page: Page, title: string): Promise<void> {
  await card(page, title).getByTestId('card-title').click()
  await expect(page.getByTestId('editor')).toBeVisible()
}

/** Sets the title of the open note and closes the editor, which saves at once. */
export async function retitle(page: Page, from: string, to: string): Promise<void> {
  await openNote(page, from)
  await page.getByTestId('editor-title').fill(to)
  await page.getByTestId('close-note').click()
  await expect(page.getByTestId('editor')).toHaveCount(0)
}

export async function accountMenu(page: Page, item: string): Promise<void> {
  await page.getByTestId('account-menu').click()
  await page.getByRole('menuitem', { name: item }).click()
}

/** The admin signed in on a context of their own, on the administration page. */
export async function adminPage(browser: Browser) {
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto('/login')
  await page.getByLabel('E-mail').fill(admin.email)
  await page.getByLabel('Password').fill(admin.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByTestId('sync-status')).toBeVisible()
  await page.goto('/admin')
  return { context, page }
}
