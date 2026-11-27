import { createHmac } from 'node:crypto'
import { expect, test } from '@playwright/test'
import { addNote, admin, newUser, signedIn } from './helpers'

/** RFC 6238 TOTP for a base32 secret, as an authenticator app computes it. */
function totp(secret: string, at = Date.now()): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  let bits = ''
  for (const char of secret.replace(/=+$/, '')) {
    bits += alphabet.indexOf(char).toString(2).padStart(5, '0')
  }
  const key = Buffer.from(bits.match(/.{8}/g)!.map((byte) => parseInt(byte, 2)))
  const counter = Buffer.alloc(8)
  counter.writeBigUInt64BE(BigInt(Math.floor(at / 30_000)))
  const hash = createHmac('sha1', key).update(counter).digest()
  const offset = hash[hash.length - 1] & 0xf
  const value = (hash.readUInt32BE(offset) & 0x7fffffff) % 1_000_000
  return value.toString().padStart(6, '0')
}

test('two-step verification is set up in settings and asked for at sign-in', async ({
  browser,
}) => {
  const user = await newUser(browser)
  const { page } = await signedIn(browser, user)
  await page.goto('/settings/security')
  await page.getByTestId('totp-start').click()
  const secret = (await page.getByTestId('totp-secret').textContent())!.trim()
  await page.getByLabel('Enter the 6-digit code it shows').fill(totp(secret))
  await page.getByRole('button', { name: 'Turn on' }).click()
  const codes = page.getByTestId('recovery-codes').getByRole('listitem')
  await expect(codes).toHaveCount(10)
  const recovery = (await codes.first().textContent())!.trim()
  await page.getByRole('button', { name: 'Done' }).click()
  await expect(page.getByTestId('totp-settings')).toContainText('10 recovery codes left')

  // A fresh browser needs the password and then a code; a recovery code does too.
  const context = await browser.newContext()
  const login = await context.newPage()
  await login.goto('/login')
  await login.getByLabel('E-mail').fill(user.email)
  await login.getByLabel('Password').fill(user.password)
  await login.getByRole('button', { name: 'Sign in' }).click()
  await expect(login.getByTestId('totp-step')).toBeVisible()
  await expect(login.getByLabel('Code')).toBeFocused()
  await login.getByLabel('Code').fill('000000')
  await login.getByRole('button', { name: 'Verify' }).click()
  await expect(login.getByRole('alert')).toContainText('The code is not correct')
  await login.getByLabel('Code').fill(recovery)
  await login.getByRole('button', { name: 'Verify' }).click()
  await expect(login.getByTestId('sync-status')).toBeVisible()
  await context.close()
})

test('a read token lists notes and is refused when it writes or touches tokens', async ({
  browser,
}) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await page.goto('/settings/tokens')
  const docs = page.getByTestId('api-docs')
  expect((await page.request.get((await docs.getAttribute('href'))!)).status()).toBe(200)
  await page.getByLabel('Name').fill('Reader')
  await page.getByRole('button', { name: 'Create token' }).click()
  const token = await page.getByTestId('new-token').getByRole('textbox').inputValue()
  expect(token).toMatch(/^ntk_/)
  await expect(page.getByTestId('tokens')).toContainText('Reader')

  // A bare client, as curl would be: no cookies, only the token.
  const request = await browser.newContext()
  const headers = { Authorization: `Bearer ${token}` }
  const list = await request.request.get('/api/v1/notes', { headers })
  expect(list.status()).toBe(200)
  expect(((await list.json()) as { total: number }).total).toBe(0)
  const write = await request.request.post('/api/v1/notes', { headers, data: { title: 'x' } })
  expect(write.status()).toBe(403)
  const tokens = await request.request.get('/api/v1/me/tokens', { headers })
  expect(tokens.status()).toBe(403)
  await request.close()

  await page.getByRole('button', { name: 'Revoke' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Revoke' }).click()
  await expect(page.getByTestId('tokens')).toHaveCount(0)
})

test('an admin deactivates a user, who is then signed out', async ({ browser }) => {
  const user = await newUser(browser)
  const victim = await signedIn(browser, user)
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto('/login')
  await page.getByLabel('E-mail').fill(admin.email)
  await page.getByLabel('Password').fill(admin.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByTestId('sync-status')).toBeVisible()
  await page.goto('/admin')
  const row = page.getByRole('listitem').filter({ hasText: user.email })
  await row.getByTestId('user-actions').click()
  await page.getByRole('menuitem', { name: 'Create password reset link' }).click()
  await expect(page.getByTestId('reset-link').getByRole('textbox')).toHaveValue(/\/reset\//)
  await row.getByTestId('user-actions').click()
  await page.getByRole('menuitem', { name: 'Deactivate' }).click()
  await expect(row).toContainText('Deactivated')

  const me = await victim.context.request.get('/api/v1/me')
  expect(me.status()).toBe(401)
  await context.close()
})

test('a user deletes their own account', async ({ browser }) => {
  const user = await newUser(browser)
  const { page } = await signedIn(browser, user)
  await addNote(page, 'Soon gone')
  await expect(page.getByTestId('unsent')).toHaveCount(0)
  await page.goto('/settings/security')
  const section = page.getByTestId('delete-account')
  await section.getByRole('button', { name: 'Delete account' }).click()
  await section.getByLabel('Password').fill(user.password)
  await section.getByRole('button', { name: 'Delete account' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Delete account' }).click()
  await expect(page).toHaveURL(/\/login$/)

  const login = await page.request.post('/api/v1/auth/login', {
    data: { email: user.email, password: user.password },
  })
  expect(login.status()).toBe(401)
})
