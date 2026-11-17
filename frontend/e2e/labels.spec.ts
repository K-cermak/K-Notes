import { expect, test } from '@playwright/test'
import { addNote, card, newUser, signedIn } from './helpers'

async function labelNote(page: import('@playwright/test').Page, title: string, label: string) {
  await card(page, title).hover()
  await card(page, title).getByRole('button', { name: 'More' }).click()
  await page.getByRole('menuitem', { name: 'Add label' }).click()
  const picker = page.getByTestId('label-picker')
  // The filter field has the focus, so typing goes straight into it.
  await expect(picker.getByRole('textbox')).toBeFocused()
  await page.keyboard.type(label)
  const create = picker.getByTestId('create-label')
  if (await create.isVisible()) await create.click()
  else await picker.getByText(label, { exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(card(page, title).getByTestId('label-chip')).toContainText([label])
}

test('renaming and deleting a label reaches the other device', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)
  await addNote(a.page, 'Quarterly report')
  await labelNote(a.page, 'Quarterly report', 'Work')
  await expect(card(b.page, 'Quarterly report').getByTestId('label-chip')).toHaveText(['Work'])
  await expect(b.page.getByRole('link', { name: 'Work' })).toBeVisible()

  await a.page.getByTestId('edit-labels-button').click()
  const dialog = a.page.getByTestId('edit-labels')
  await dialog.getByTestId('label-name').fill('Office')
  await dialog.getByTestId('label-name').press('Enter')
  await expect(card(b.page, 'Quarterly report').getByTestId('label-chip')).toHaveText(['Office'])

  await dialog.getByTestId('label-name').hover()
  await dialog.getByTestId('delete-label').click()
  await expect(a.page.getByTestId('snackbar')).toContainText('Label deleted')
  await dialog.getByRole('button', { name: 'Done' }).click()
  await expect(card(b.page, 'Quarterly report').getByTestId('label-chip')).toHaveCount(0)
  await expect(card(b.page, 'Quarterly report')).toBeVisible()
  await expect(b.page.getByRole('link', { name: 'Office' })).toHaveCount(0)
})

test('undo brings a deleted label back onto its notes', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await addNote(page, 'Recipe')
  await labelNote(page, 'Recipe', 'Kitchen')
  await page.getByTestId('edit-labels-button').click()
  await page.getByTestId('edit-labels').getByTestId('label-name').hover()
  await page.getByTestId('edit-labels').getByTestId('delete-label').click()
  await page.getByTestId('snackbar').getByRole('button', { name: 'Undo' }).click()
  await page.getByTestId('edit-labels').getByRole('button', { name: 'Done' }).click()
  await expect(card(page, 'Recipe').getByTestId('label-chip')).toHaveText(['Kitchen'])
})

test('a note written in a label view gets that label', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await addNote(page, 'First')
  await labelNote(page, 'First', 'Ideas')
  await page.getByRole('link', { name: 'Ideas', exact: true }).click()
  await addNote(page, 'Second')
  await expect(card(page, 'Second').getByTestId('label-chip')).toHaveText(['Ideas'])
  await page.getByRole('link', { name: 'Notes', exact: true }).click()
  await expect(page.getByTestId('note-card')).toHaveCount(2)
})

test('search ignores case and diacritics and skips the trash', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await addNote(page, 'Pan Černý', 'Zavolat ve středu')
  await addNote(page, 'Archived Černý')
  await card(page, 'Archived Černý').hover()
  await card(page, 'Archived Černý').getByRole('button', { name: 'Archive' }).click()
  await addNote(page, 'Trashed Černý')
  await card(page, 'Trashed Černý').hover()
  await card(page, 'Trashed Černý').getByRole('button', { name: 'More' }).click()
  await page.getByRole('menuitem', { name: 'Delete note' }).click()
  // A closing menu still takes keys for its type-ahead; shortcuts work once it is gone.
  await expect(page.getByRole('menu')).toHaveCount(0)
  await expect(card(page, 'Trashed Černý')).toHaveCount(0)

  await page.keyboard.press('/')
  await page.keyboard.type('cerny')
  await expect(page).toHaveURL(/\/search\?q=cerny/)
  await expect(page.getByTestId('card-title')).toHaveText(['Pan Černý', 'Archived Černý'])
  await expect(page.getByRole('heading', { name: 'Archive', exact: true })).toBeVisible()

  await page.getByTestId('search').fill('STREDU')
  await expect(page.getByTestId('card-title')).toHaveText(['Pan Černý'])
  await page.getByTestId('search').fill('nothing like this')
  await expect(page.getByText('No matching notes')).toBeVisible()
  await page.getByTestId('search').press('Escape')
  await expect(page).toHaveURL(/\/$/)
})
