import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { addNote, admin, card, openNote, signedIn } from './helpers'

// One after another: they share the admin's notes, and a note another test adds would arrive over
// the live sync mid-check, halfway through its entrance, and fail the contrast rule.
test.describe.configure({ mode: 'serial' })

/** Fails with axe's findings, as rule, impact and the elements involved, so the report is readable. */
async function expectAccessible(page: Page, where: string): Promise<void> {
  // Mid-animation colours are blends of the final ones, which axe would measure instead.
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  )
  const { violations } = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze()
  const found = violations.map(
    (v) =>
      `${where}: ${v.id} (${v.impact}) ${v.help}\n` +
      v.nodes
        .map((n) => `    ${n.target.join(' ')}: ${n.any[0]?.message ?? n.failureSummary}`)
        .join('\n'),
  )
  // Soft, so that one run lists the findings of every screen.
  expect.soft(found, found.join('\n')).toEqual([])
}

for (const colorScheme of ['light', 'dark'] as const) {
  test(`the main screens pass an accessibility check in the ${colorScheme} theme`, async ({
    browser,
  }) => {
    const { page } = await signedIn(browser, admin)
    await page.emulateMedia({ colorScheme })
    const title = `Accessible ${colorScheme}`
    await addNote(page, title, 'Body text')
    await card(page, title).hover()
    await card(page, title).getByRole('button', { name: 'Background colour' }).click()
    await page.getByRole('radio', { name: 'Coral' }).click()
    await page.keyboard.press('Escape')
    await expectAccessible(page, 'notes')

    await card(page, title).hover()
    await card(page, title).getByRole('button', { name: 'More' }).click()
    await expectAccessible(page, 'note menu')
    await page.keyboard.press('Escape')

    await card(page, title).hover()
    await card(page, title).getByRole('button', { name: 'Select note' }).click()
    await expect(page.getByTestId('selection-bar')).toBeVisible()
    await expectAccessible(page, 'selection')
    await page.keyboard.press('Escape')

    await page.getByTestId('edit-labels-button').click()
    await expect(page.getByTestId('edit-labels')).toBeVisible()
    await expectAccessible(page, 'edit labels')
    await page.keyboard.press('Escape')

    await openNote(page, title)
    await expectAccessible(page, 'editor')
    await page.getByTestId('close-note').click()
    // Closing goes back in the history; a navigation started before that is done gets aborted.
    await expect(page).not.toHaveURL(/\/note\//)

    for (const path of [
      '/archive',
      '/trash',
      '/search?q=accessible',
      '/settings/profile',
      '/settings/security',
      '/settings/tokens',
      '/settings/device',
      '/admin',
    ]) {
      await page.goto(path)
      await expect(page.locator('main, [role=main]').first()).toBeVisible()
      await expectAccessible(page, path)
    }
  })
}

test('tabbing through the search field leads on to the notes', async ({ browser }) => {
  const { page } = await signedIn(browser, admin)
  await page.getByTestId('search').focus()
  await page.keyboard.press('Tab')
  await expect(page).toHaveURL(/\/$/)
  await page.getByTestId('composer').focus()
  await expect(page.getByTestId('composer')).toBeFocused()
  await page.getByTestId('search').focus()
  await page.keyboard.type('x')
  await expect(page).toHaveURL(/\/search\?q=x$/)
})

test('the sign-in page passes an accessibility check', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByLabel('E-mail')).toBeVisible()
  await expectAccessible(page, 'login')
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })

  test('the notes and the editor pass an accessibility check', async ({ browser }) => {
    const { page } = await signedIn(browser, admin)
    await page.setViewportSize({ width: 390, height: 844 })
    await expectAccessible(page, 'phone notes')
    await page.getByTestId('note-card').first().click()
    await expect(page.getByTestId('editor')).toBeVisible()
    await expectAccessible(page, 'phone editor')
  })
})
