import { expect, test, type Locator, type Page } from '@playwright/test'
import { card, newUser, openNote, signedIn } from './helpers'

/** Writes a checklist through the composer's "New list" button, one Enter per item. */
async function addChecklist(page: Page, title: string, items: string[]): Promise<void> {
  await page.getByTestId('composer-list').click()
  const form = page.getByTestId('note-form')
  await expect(form.getByTestId('add-item')).toBeFocused()
  await page.keyboard.type(items.join('\n'))
  await form.getByTestId('editor-title').fill(title)
  await expect(form.getByTestId('item-text')).toHaveCount(items.length)
  await form.getByTestId('close-note').click()
  await expect(page.getByTestId('note-form')).toHaveCount(0)
  await expect(card(page, title).getByTestId('card-items')).toContainText(items.at(-1)!)
}

function itemTexts(scope: Locator) {
  return scope
    .getByTestId('item-text')
    .evaluateAll((fields) => fields.map((f) => (f as HTMLTextAreaElement).value))
}

function item(scope: Locator, text: string) {
  return scope
    .getByTestId('checklist-item')
    .filter({ has: scope.page().getByRole('checkbox', { name: text, exact: true }) })
}

test('an existing checklist opens in its new item field', async ({ browser }) => {
  const { page } = await signedIn(browser, await newUser(browser))
  await addChecklist(page, 'Packing', ['Tent'])
  await page.reload()
  await openNote(page, 'Packing')
  await expect(page.getByTestId('editor').getByTestId('add-item')).toBeFocused()
})

test('a checklist is written, checked, edited and reordered', async ({ browser }) => {
  const user = await newUser(browser)
  const { page } = await signedIn(browser, user)
  await addChecklist(page, 'Groceries', ['Milk', 'Bread', 'Eggs'])

  await openNote(page, 'Groceries')
  const editor = page.getByTestId('editor')
  await item(editor, 'Bread').getByTestId('item-checkbox').click()
  await expect(editor.getByTestId('checked-toggle')).toHaveText('1 checked item')
  await expect.poll(() => itemTexts(editor)).toEqual(['Milk', 'Eggs', 'Bread'])

  // Enter in the middle splits an item; Backspace in an empty item removes it.
  await item(editor, 'Eggs').getByTestId('item-text').click()
  await page.keyboard.press('End')
  await page.keyboard.press('ArrowLeft')
  await page.keyboard.press('Enter')
  await expect.poll(() => itemTexts(editor)).toEqual(['Milk', 'Egg', 's', 'Bread'])
  await page.keyboard.press('Delete')
  await page.keyboard.press('Backspace')
  await expect.poll(() => itemTexts(editor)).toEqual(['Milk', 'Egg', 'Bread'])
  await expect(item(editor, 'Egg').getByTestId('item-text')).toBeFocused()

  // Several pasted lines become several items.
  await editor.getByTestId('add-item').evaluate((field) => {
    const data = new DataTransfer()
    data.setData('text/plain', 'Apples\n\nPears\r\nPlums')
    field.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, cancelable: true }))
  })
  await expect
    .poll(() => itemTexts(editor))
    .toEqual(['Milk', 'Egg', 'Apples', 'Pears', 'Plums', 'Bread'])

  // Dragging the handle of Plums to the top. Sortable checks the pointer about every 50 ms, so
  // the drag moves in small steps and drops only once the list shows the new order, as a hand would.
  const plums = item(editor, 'Plums')
  await plums.hover()
  const handle = (await plums.locator('.drag-handle').boundingBox())!
  const top = (await item(editor, 'Milk').boundingBox())!
  const x = handle.x + handle.width / 2
  const from = handle.y + handle.height / 2
  await page.mouse.move(x, from)
  await page.mouse.down()
  for (let step = 1; step <= 10; step++) {
    await page.mouse.move(x, from + ((top.y + 4 - from) * step) / 10)
    await page.waitForTimeout(30)
  }
  await expect.poll(async () => (await itemTexts(editor))[0]).toBe('Plums')
  await page.mouse.up()
  await expect
    .poll(() => itemTexts(editor))
    .toEqual(['Plums', 'Milk', 'Egg', 'Apples', 'Pears', 'Bread'])

  await page.getByTestId('close-note').click()
  await expect(card(page, 'Groceries').getByTestId('card-checked')).toHaveText('1 checked item')
  // The checked items open right on the card, without opening the note, and stay open.
  const checkedOnCard = card(page, 'Groceries').getByRole('checkbox', { checked: true })
  await expect(checkedOnCard).toHaveCount(0)
  await card(page, 'Groceries').getByTestId('card-checked').click()
  await expect(page.getByTestId('editor')).toHaveCount(0)
  await expect(checkedOnCard).toHaveCount(1)
  await expect(page.getByTestId('unsent')).toHaveCount(0)
  await page.reload()
  await expect(checkedOnCard).toHaveCount(1)
  await openNote(page, 'Groceries')
  await expect
    .poll(() => itemTexts(page.getByTestId('editor')))
    .toEqual(['Plums', 'Milk', 'Egg', 'Apples', 'Pears', 'Bread'])

  // The card and the editor share whether the checked items are shown.
  const checkedInEditor = item(page.getByTestId('editor'), 'Bread')
  await expect(checkedInEditor).toBeVisible()
  await page.getByTestId('checked-toggle').click()
  await expect(checkedInEditor).toBeHidden()
  await page.getByTestId('close-note').click()
  await expect(checkedOnCard).toHaveCount(0)
})

test('a text note converts to a checklist and back', async ({ browser }) => {
  const user = await newUser(browser)
  const { page } = await signedIn(browser, user)
  await page.getByTestId('composer').click()
  await page.getByTestId('editor-title').fill('Packing')
  await page.getByTestId('editor-body').click()
  await page.keyboard.type('Passport\n\nCharger')
  await page.getByTestId('close-note').click()
  await expect(card(page, 'Packing').getByTestId('card-body')).toContainText('Charger')

  await card(page, 'Packing').hover()
  await card(page, 'Packing').getByRole('button', { name: 'More' }).click()
  await page.getByRole('menuitem', { name: 'Show checkboxes' }).click()
  const items = card(page, 'Packing').getByTestId('card-items')
  await expect(items).toContainText('Passport')
  await card(page, 'Packing').getByRole('checkbox', { name: 'Charger' }).click()
  await expect(card(page, 'Packing').getByTestId('card-checked')).toHaveText('1 checked item')

  await openNote(page, 'Packing')
  await page.getByTestId('editor').getByRole('button', { name: 'More' }).click()
  await page.getByRole('menuitem', { name: 'Hide checkboxes' }).click()
  await expect(page.getByTestId('editor-body')).toHaveText(/^Passport\s*Charger$/)
  await page.getByTestId('close-note').click()
  await expect(card(page, 'Packing').getByTestId('card-items')).toHaveCount(0)
})

test('the l key starts a checklist', async ({ browser }) => {
  const user = await newUser(browser)
  const { page } = await signedIn(browser, user)
  await page.keyboard.press('l')
  await expect(page.getByTestId('add-item')).toBeFocused()
  await page.keyboard.type('First')
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('note-card').getByTestId('card-items')).toHaveText('First')
})

test('two offline clients checking different items both keep their changes', async ({
  browser,
}) => {
  const user = await newUser(browser)
  const a = await signedIn(browser, user)
  const b = await signedIn(browser, user)
  await addChecklist(a.page, 'Trip', ['Tickets', 'Tent', 'Torch'])
  await expect(card(b.page, 'Trip').getByTestId('card-items')).toContainText('Torch')

  await a.context.setOffline(true)
  await b.context.setOffline(true)
  await card(a.page, 'Trip').getByRole('checkbox', { name: 'Tickets' }).click()
  await card(b.page, 'Trip').getByRole('checkbox', { name: 'Torch' }).click()
  await expect(a.page.getByTestId('unsent')).toBeVisible()
  await expect(b.page.getByTestId('unsent')).toBeVisible()

  await a.context.setOffline(false)
  await expect(a.page.getByTestId('unsent')).toHaveCount(0)
  await b.context.setOffline(false)
  await expect(b.page.getByTestId('unsent')).toHaveCount(0)

  for (const page of [a.page, b.page]) {
    await expect(card(page, 'Trip').getByTestId('card-items')).toContainText('Tent')
    await expect(card(page, 'Trip').getByTestId('card-checked')).toHaveText('2 checked items')
    await expect(card(page, 'Trip').getByTestId('card-items')).not.toContainText('Tickets')
  }
  await expect(a.page.getByTestId('note-card')).toHaveCount(1)
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 760 }, hasTouch: true, isMobile: true })

  test('a list is started from its own button above the new note button', async ({ browser }) => {
    const { page } = await signedIn(browser, await newUser(browser))
    await page.getByTestId('fab-list').tap()
    const editor = page.getByTestId('editor')
    await expect(editor.getByTestId('add-item')).toBeFocused()
    await page.keyboard.type('Bread')
    await editor.getByTestId('editor-title').fill('Bakery')
    await editor.getByTestId('close-note').tap()
    await expect(card(page, 'Bakery').getByTestId('card-items')).toHaveText('Bread')
  })
})
