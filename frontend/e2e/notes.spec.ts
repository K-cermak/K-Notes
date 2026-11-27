import { expect, test } from '@playwright/test'
import { addNote, card, newUser, openNote, signedIn } from './helpers'

test('editing an existing note right after opening it keeps its text', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await addNote(page, 'Groceries', 'Milk')
  await page.reload()
  await openNote(page, 'Groceries')
  await page.getByTestId('editor-body').click()
  await page.keyboard.press('Control+End')
  await page.keyboard.type(' and eggs')
  await page.keyboard.press('Escape')
  await expect(card(page, 'Groceries').getByTestId('card-body')).toHaveText('Milk and eggs')
})

test('formatting applies to the text typed next', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await page.getByTestId('composer').click()
  await page.getByTestId('editor-title').fill('Formatted')
  await page.getByTestId('editor-body').click()
  // Escape closes the menu alone, though the focus stays in the editor while it is open.
  await page.getByTestId('note-form').getByRole('button', { name: 'Formatting' }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Heading 1' })).toHaveCount(0)
  await expect(page.getByTestId('note-form')).toBeVisible()
  await page.getByTestId('note-form').getByRole('button', { name: 'Formatting' }).click()
  await page.getByRole('button', { name: 'Heading 1' }).click()
  await page.keyboard.type('Big')
  await page.keyboard.press('Enter')
  await page.keyboard.press('ControlOrMeta+b')
  await page.keyboard.type('bold')
  await page.getByTestId('close-note').click()
  const body = card(page, 'Formatted').getByTestId('card-body')
  await expect(body.locator('h3')).toHaveText('Big')
  await expect(body.locator('strong')).toHaveText('bold')
})

test('archive and trash with undo, restore and delete forever', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await addNote(page, 'Old receipt')
  await card(page, 'Old receipt').hover()
  await card(page, 'Old receipt').getByRole('button', { name: 'Pin note' }).click()

  await card(page, 'Old receipt').hover()
  await card(page, 'Old receipt').getByRole('button', { name: 'Archive' }).click()
  await expect(page.getByTestId('snackbar')).toContainText('Note archived')
  await expect(card(page, 'Old receipt')).toHaveCount(0)
  await page.getByTestId('snackbar').getByRole('button', { name: 'Undo' }).click()
  await expect(card(page, 'Old receipt')).toBeVisible()
  // Archiving unpins; Undo pins it again.
  await card(page, 'Old receipt').hover()
  await expect(card(page, 'Old receipt').getByRole('button', { name: 'Unpin note' })).toBeVisible()

  await card(page, 'Old receipt').hover()
  await card(page, 'Old receipt').getByRole('button', { name: 'More' }).click()
  await page.getByRole('menuitem', { name: 'Delete note' }).click()
  await expect(card(page, 'Old receipt')).toHaveCount(0)
  await page.getByRole('link', { name: 'Trash' }).click()
  await expect(page.getByText('Notes in the trash are deleted after 7 days.')).toBeVisible()

  await card(page, 'Old receipt').hover()
  await card(page, 'Old receipt').getByRole('button', { name: 'Restore' }).click()
  await expect(page.getByTestId('empty-state')).toBeVisible()
  await page.getByRole('link', { name: 'Notes', exact: true }).click()
  await expect(card(page, 'Old receipt')).toBeVisible()
})

test('the composer follows a new note once it is saved', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await page.getByTestId('composer').click()
  const form = page.getByTestId('note-form')
  await form.getByTestId('editor-title').fill('Pinned draft')
  await expect(page.getByTestId('note-card')).toHaveCount(1)
  const pin = form.getByRole('button', { name: 'Pin note' })
  await pin.click()
  await expect(form.getByRole('button', { name: 'Unpin note' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await form.getByRole('button', { name: 'Unpin note' }).click()
  await expect(pin).toHaveAttribute('aria-pressed', 'false')
})

test('an empty new note is discarded when closed', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await page.keyboard.press('c')
  await expect(page.getByTestId('note-form')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('note-card')).toHaveCount(0)
  await expect(page.getByTestId('empty-state')).toBeVisible()
})

test('the theme is saved in the profile and follows the user', async ({ browser }) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  await a.page.getByRole('button', { name: 'Display options' }).click()
  await a.page.getByRole('menuitemradio', { name: 'Dark' }).click()
  await expect(a.page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await a.page.reload()
  await expect(a.page.locator('html')).toHaveAttribute('data-theme', 'dark')
  const b = await signedIn(browser, user)
  await expect(b.page.locator('html')).toHaveAttribute('data-theme', 'dark')
})

test('a message replacing another one shows in the same place', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  for (const title of ['First', 'Second']) await addNote(page, title)
  for (const title of ['First', 'Second']) {
    await card(page, title).hover()
    await card(page, title).getByRole('button', { name: 'Archive' }).click()
  }
  // Both are on screen for a moment: the first leaving, the second arriving.
  const lefts = await page
    .getByTestId('snackbar')
    .evaluateAll((bars) => bars.map((bar) => Math.round(bar.getBoundingClientRect().left)))
  expect(new Set(lefts).size).toBe(1)
})

test('a new note starts in its text, and Tab leads from the title to the text', async ({
  browser,
}) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await page.getByTestId('composer').click()
  const form = page.getByTestId('note-form')
  await expect(form.getByTestId('editor-body')).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(form.getByTestId('editor-title')).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(form.getByTestId('editor-body')).toBeFocused()

  await page.keyboard.press('Escape')
  await page.getByTestId('composer-list').click()
  await form.getByTestId('editor-title').click()
  await page.keyboard.press('Tab')
  await expect(form.getByTestId('add-item')).toBeFocused()
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })

  test('a new note starts in its text and the back arrow saves and closes it', async ({
    browser,
  }) => {
    const { page } = await signedIn(browser, await newUser(browser))
    await page.getByTestId('fab').click()
    await expect(page.getByTestId('editor-body')).toBeFocused()
    await page.keyboard.type('Written on the phone')
    await page.getByTestId('editor-back').click()
    await expect(page.getByTestId('editor')).toHaveCount(0)
    await expect(
      page.getByTestId('note-card').filter({ hasText: 'Written on the phone' }),
    ).toBeVisible()
  })
})
