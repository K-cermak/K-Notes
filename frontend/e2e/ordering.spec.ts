import { expect, test, type Locator, type Page } from '@playwright/test'
import { addNote, card, newUser, signedIn } from './helpers'

function titles(page: Page) {
  return page
    .getByTestId('note-card')
    .evaluateAll((cards) => cards.map((c) => c.getAttribute('aria-label')))
}

/** A card's box once it has stopped moving: cards glide to new places for 200 ms. */
async function settledBox(locator: Locator) {
  let previous = ''
  for (;;) {
    const box = (await locator.boundingBox())!
    if (JSON.stringify(box) === previous) return box
    previous = JSON.stringify(box)
    await locator.page().waitForTimeout(60)
  }
}

/** Drags a card by mouse onto another card's place, in small steps as a hand would. */
async function dragCard(page: Page, from: string, to: string): Promise<void> {
  const start = await settledBox(card(page, from))
  const end = await settledBox(card(page, to))
  const x = start.x + start.width / 2
  const y = start.y + 20
  await page.mouse.move(x, y)
  await page.mouse.down()
  for (let step = 1; step <= 12; step++) {
    await page.mouse.move(
      x + ((end.x + end.width / 2 - x) * step) / 12,
      y + ((end.y + 20 - y) * step) / 12,
    )
    await page.waitForTimeout(16)
  }
  await page.mouse.up()
}

test('a note dragged to a new place stays there and moves on the other device', async ({
  browser,
}) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)
  for (const title of ['One', 'Two', 'Three']) await addNote(a.page, title)
  await expect.poll(() => titles(a.page)).toEqual(['Three', 'Two', 'One'])
  await expect.poll(() => titles(b.page)).toEqual(['Three', 'Two', 'One'])

  await dragCard(a.page, 'One', 'Three')
  await expect.poll(() => titles(a.page)).toEqual(['One', 'Three', 'Two'])
  // The drop does not count as a click that opens the note.
  await expect(a.page.getByTestId('editor')).toHaveCount(0)
  await expect.poll(() => titles(b.page)).toEqual(['One', 'Three', 'Two'])
  await expect(a.page.getByTestId('unsent')).toHaveCount(0)
  await a.page.reload()
  await expect.poll(() => titles(a.page)).toEqual(['One', 'Three', 'Two'])
})

test.describe('on a touch screen', () => {
  // Short enough that the notes overflow it, so a scroll is possible at all.
  test.use({ viewport: { width: 390, height: 320 }, hasTouch: true, isMobile: true })

  test('a long-press selects a note and dragging it does not scroll the page', async ({
    browser,
  }) => {
    const user = await newUser(browser)
    const { page, context } = await signedIn(browser, user)
    await addNotesOnPhone(page, ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'])
    await expect.poll(() => titles(page)).toEqual(['H', 'G', 'F', 'E', 'D', 'C', 'B', 'A'])

    const touch = await context.newCDPSession(page)
    const start = await settledBox(card(page, 'F'))
    const end = await settledBox(card(page, 'H'))
    const point = (x: number, y: number) => [{ x, y, id: 1 }]
    const x = start.x + start.width / 2
    const y = start.y + 20
    await touch.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: point(x, y) })
    await page.waitForTimeout(700)
    await expect(page.getByTestId('selection-count')).toHaveText('1 selected')
    for (let step = 1; step <= 12; step++) {
      await touch.send('Input.dispatchTouchEvent', {
        type: 'touchMove',
        touchPoints: point(
          x + ((end.x + end.width / 2 - x) * step) / 12,
          y + ((end.y + 20 - y) * step) / 12,
        ),
      })
      await page.waitForTimeout(16)
    }
    await touch.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })

    await expect.poll(() => titles(page)).toEqual(['F', 'H', 'G', 'E', 'D', 'C', 'B', 'A'])
    expect(await page.evaluate(() => window.scrollY)).toBe(0)
    expect(await page.evaluate(() => window.getSelection()?.toString() ?? '')).toBe('')
    await expect(page.getByTestId('editor')).toHaveCount(0)
    await expect(page.getByTestId('selection-count')).toHaveText('1 selected')

    // The same gesture without the long-press is an ordinary scroll.
    await touch.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: point(x, 280) })
    for (let step = 1; step <= 10; step++) {
      await touch.send('Input.dispatchTouchEvent', {
        type: 'touchMove',
        touchPoints: point(x, 280 - step * 20),
      })
      await page.waitForTimeout(16)
    }
    await touch.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0)
    await expect.poll(() => titles(page)).toEqual(['F', 'H', 'G', 'E', 'D', 'C', 'B', 'A'])
  })
})

async function addNotesOnPhone(page: Page, list: string[]): Promise<void> {
  for (const title of list) {
    await page.getByTestId('fab').click()
    await page.getByTestId('editor-title').fill(title)
    await page.getByTestId('close-note').click()
    await expect(page.getByTestId('editor')).toHaveCount(0)
    await expect(card(page, title)).toBeVisible()
  }
}

test('several notes archived together come back with one Undo', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  for (const title of ['Keep', 'Old 1', 'Old 2', 'Old 3']) await addNote(page, title)

  await card(page, 'Old 1').hover()
  await card(page, 'Old 1').getByTestId('card-select').click()
  await card(page, 'Old 3').click({ modifiers: ['Shift'] })
  await expect(page.getByTestId('selection-count')).toHaveText('3 selected')
  await page.getByTestId('selection-archive').click()
  await expect(page.getByTestId('selection-bar')).toHaveCount(0)
  await expect.poll(() => titles(page)).toEqual(['Keep'])

  await page.getByRole('button', { name: 'Undo' }).click()
  await expect.poll(() => titles(page)).toEqual(['Old 3', 'Old 2', 'Old 1', 'Keep'])
})

test('labels are added to several selected notes at once', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  for (const title of ['First', 'Second']) await addNote(page, title)
  await card(page, 'First').hover()
  await card(page, 'First').getByTestId('card-select').click()
  await card(page, 'Second').click()
  await page.getByRole('button', { name: 'Change labels' }).click()
  const picker = page.getByTestId('label-picker')
  await picker.getByRole('textbox').fill('Shared')
  await picker.getByTestId('create-label').click()
  await page.keyboard.press('Escape')
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('selection-bar')).toHaveCount(0)
  for (const title of ['First', 'Second']) {
    await expect(card(page, title)).toContainText('Shared')
  }
})

test('a rectangle drawn over empty space selects the notes it touches', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  for (const title of ['Left out', 'Second', 'First']) await addNote(page, title)
  const first = await settledBox(card(page, 'First'))
  const second = await settledBox(card(page, 'Second'))

  // From the empty space above and left of the first card to the middle of the second one.
  await page.mouse.move(first.x - 12, first.y - 12)
  await page.mouse.down()
  for (let step = 1; step <= 8; step++) {
    await page.mouse.move(
      first.x - 12 + ((second.x + second.width / 2 - first.x + 12) * step) / 8,
      first.y - 12 + ((second.y + second.height / 2 - first.y + 12) * step) / 8,
    )
  }
  await expect(page.getByTestId('marquee')).toBeVisible()
  await page.mouse.up()
  await expect(page.getByTestId('marquee')).toHaveCount(0)
  await expect(page.getByTestId('selection-count')).toHaveText('2 selected')
  await expect(card(page, 'Left out').getByTestId('card-select')).toHaveAttribute(
    'aria-pressed',
    'false',
  )
  // The release does not count as a click on the empty space or a note.
  await expect(page.getByTestId('editor')).toHaveCount(0)
  await expect(page.getByTestId('selection-count')).toHaveText('2 selected')

  // A click on empty space clears the selection.
  await page.mouse.click(first.x - 12, first.y - 12)
  await expect(page.getByTestId('selection-bar')).toHaveCount(0)
  await card(page, 'First').hover()
  await card(page, 'First').getByTestId('card-select').click()

  // Starting on a note drags the note instead.
  await page.keyboard.press('Escape')
  const third = await settledBox(card(page, 'Left out'))
  await page.mouse.move(third.x + third.width / 2, third.y + 20)
  await page.mouse.down()
  await page.mouse.move(third.x + third.width / 2 + 40, third.y + 60, { steps: 4 })
  await expect(page.getByTestId('marquee')).toHaveCount(0)
  await page.mouse.up()
})
