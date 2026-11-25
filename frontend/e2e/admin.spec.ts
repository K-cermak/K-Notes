import { expect, test } from '@playwright/test'
import { adminPage } from './helpers'

// The limits apply to the whole instance while other tests run in parallel, so this one saves
// only the sign-in length, which no other test depends on, and puts it back.
test('an admin sets the instance limits, and shortening the trash period asks first', async ({
  browser,
}) => {
  const { page } = await adminPage(browser)
  const form = page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: 'Limits' }) })
  const save = form.getByRole('button', { name: 'Save' })
  const days = form.getByLabel('Sign people out after inactivity (days)')
  const trash = form.getByLabel('Delete notes from the trash after (days)')
  await expect(days).toHaveValue('180')

  await days.fill('0')
  await save.click()
  await expect(form).toContainText('Enter a whole number from 1 to 3650.')

  await days.fill('90')
  await save.click()
  await expect(page.getByTestId('snackbar')).toContainText('Changes saved')
  await page.reload()
  await expect(days).toHaveValue('90')

  await trash.fill('3')
  await save.click()
  const dialog = page.getByRole('alertdialog')
  await expect(dialog).toContainText('longer than 3 days will be deleted forever')
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await page.reload()
  await expect(trash).toHaveValue('7')

  await days.fill('180')
  await save.click()
  await expect(page.getByTestId('snackbar')).toContainText('Changes saved')
})
