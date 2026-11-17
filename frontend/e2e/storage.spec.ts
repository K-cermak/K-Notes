import { expect, test, type Browser } from '@playwright/test'
import { addNote, admin, card, newUser, openNote, signedIn } from './helpers'

async function adminPage(browser: Browser) {
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

test('over the quota a user cannot create notes until they delete enough', async ({ browser }) => {
  const user = await newUser(browser)
  const { page } = await signedIn(browser, user)
  await addNote(page, 'Long one', 'x'.repeat(400))
  await expect(page.getByTestId('unsent')).toHaveCount(0)

  // An admin gives the user 0.3 KB, less than the note already takes.
  const adminSession = await adminPage(browser)
  const row = adminSession.page.getByRole('listitem').filter({ hasText: user.email })
  await row.getByTestId('user-actions').click()
  await adminSession.page.getByRole('menuitem', { name: 'Storage limit…' }).click()
  const editor = adminSession.page.getByTestId('limit-editor')
  await editor.getByLabel('Custom').check()
  await editor.getByLabel('Limit in MB').fill('0.0003')
  await editor.getByRole('button', { name: 'Save' }).click()
  await expect(row.getByTestId('user-storage')).toContainText('/ 300 B')
  await adminSession.context.close()

  await page.goto('/settings/profile')
  await expect(page.getByTestId('storage-use')).toContainText('of 300 B used')
  await page.goto('/')
  await expect(page.getByTestId('storage-full')).toBeVisible()
  await page.getByTestId('composer').click()
  await expect(page.getByTestId('snackbar')).toContainText('Your storage is full')
  await expect(page.getByTestId('note-form')).toHaveCount(0)

  // Editing an existing note is still allowed.
  await openNote(page, 'Long one')
  await page.getByTestId('editor-title').fill('Long one, edited')
  await page.getByTestId('close-note').click()
  await expect(card(page, 'Long one, edited')).toBeVisible()

  // Deleting it forever frees the space.
  await card(page, 'Long one, edited').hover()
  await card(page, 'Long one, edited').getByRole('button', { name: 'More' }).click()
  await page.getByRole('menuitem', { name: 'Delete note' }).click()
  // The move to the trash is written asynchronously; a reload before that would undo it.
  await expect(card(page, 'Long one, edited')).toHaveCount(0)
  await page.goto('/trash')
  await page.getByRole('button', { name: 'Empty trash' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Empty trash' }).click()
  await expect(page.getByTestId('empty-state')).toBeVisible()
  await expect(page.getByTestId('unsent')).toHaveCount(0)
  // The quota from before the reload shows until the first sync brings the new one.
  await page.goto('/')
  await expect(page.getByTestId('sync-status')).toHaveAttribute('data-state', 'synced')
  await expect(page.getByTestId('storage-full')).toHaveCount(0)
  await addNote(page, 'Short')
})
