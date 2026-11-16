import { expect, test } from '@playwright/test'
import { accountMenu, admin } from './helpers'

const friend = { name: 'Fred Friend', email: 'fred@example.com', password: 'friend-password' }

test('first-run setup, invite by link, sign out and sign in', async ({ page, browser }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/setup$/)
  await page.getByLabel('Display name').fill(admin.name)
  await page.getByLabel('E-mail').fill(admin.email)
  await page.getByLabel('Password').fill(admin.password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByTestId('sync-status')).toHaveAttribute('data-state', 'synced')
  await page.getByTestId('account-menu').click()
  await expect(page.getByTestId('signed-in-as')).toHaveText(admin.name)
  await page.getByRole('menuitem', { name: 'Administration' }).click()

  await page.getByRole('button', { name: 'Create invite link' }).click()
  const link = await page.locator('#invite-link').inputValue()
  expect(link).toContain('/invite/')

  const other = await browser.newContext()
  const guest = await other.newPage()
  await guest.goto(new URL(link).pathname)
  await guest.getByLabel('Display name').fill(friend.name)
  await guest.getByLabel('E-mail').fill(friend.email)
  await guest.getByLabel('Password').fill(friend.password)
  await guest.getByRole('button', { name: 'Create account' }).click()
  await expect(guest.getByTestId('composer')).toBeVisible()
  await guest.getByTestId('account-menu').click()
  await expect(guest.getByRole('menuitem', { name: 'Administration' })).toHaveCount(0)
  await guest.keyboard.press('Escape')

  await accountMenu(guest, 'Sign out')
  await expect(guest).toHaveURL(/\/login$/)
  await guest.goto('/')
  await expect(guest).toHaveURL(/\/login$/)

  await guest.getByLabel('E-mail').fill(friend.email)
  await guest.getByLabel('Password').fill('wrong-password')
  await guest.getByRole('button', { name: 'Sign in' }).click()
  await expect(guest.getByRole('alert')).toContainText('not correct')

  await guest.getByLabel('Password').fill(friend.password)
  await guest.getByRole('button', { name: 'Sign in' }).click()
  await expect(guest.getByTestId('composer')).toBeVisible()

  await guest.goto(new URL(link).pathname)
  await expect(guest.getByRole('alert')).toContainText('already been used')
  await other.close()
})
